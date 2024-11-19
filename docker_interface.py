import os
import shutil
from typing import Union
import globals
import subprocess
import random
import signal
import pexpect
import pexpect.popen_spawn
import pexpect.exceptions


'''
The shared error class in this module
'''
class DockerRuntimeError(Exception): pass


'''
The shared error class in this module
'''
class ShellFailure(Exception): pass


'''
The shared error class in this module
'''
class ShellTimeout(Exception): pass


'''
Run a non-interactive shell command on the HOST, and automatically throw error if it fails.
'''
def run_command_with_check(command: list[str]):
    cmd = subprocess.run(command, text=True, capture_output=True)
    if cmd.returncode != 0:
        raise DockerRuntimeError('Error creating container:\n' + cmd.stderr)
    return cmd


'''
Generates a random container name, prefixed by the predefined container prefix
'''
def random_container_name():
    # Do NOT include weird characters. This name is also used as the command prompt.
    s = '0123456789qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM'
    return globals.container_prefix + ''.join([
        s[random.randrange(0, len(s))]
        for i in range(0, 24)
    ])


'''
Creates a container from an image

Returns the container interface object.
'''
def create_container_from_image(container_name: str, image_name: str):
    run_command_with_check([
        globals.docker_executable, 'create',
        '-it',
        '--name', container_name,
        image_name
    ])
    return ContainerInterface(container_name)


'''
The interface to a container name, which could be running or not.

It takes no ownership of the container. Remember to call `rm` manually if this container is no longer needed.

**Always remember to handle potential DockerRuntimeError!**
'''
class ContainerInterface:
    def __init__(self, name: str):
        self.name = name
    
    
    '''
    Start the container. Do this before interacting with the container.
    '''
    def start(self):
        run_command_with_check([
            globals.docker_executable, 'start', self.name
        ])
        

    '''
    Stop the container.
    '''
    def stop(self):
        run_command_with_check([
            globals.docker_executable, 'stop', self.name
        ])
        
        
    '''
    Forcefully and quickly stop the container.
    
    It is recommended to kill before deleting if the container is no longer needed. This prevents wasting time on trying to shut down the container gracefully.
    '''
    def kill(self):
        run_command_with_check([
            globals.docker_executable, 'kill', self.name
        ])
    
        
    '''
    Delete the container forcefully
    
    Note that this will not be called when the container interface is destroyed. You must do it manually.
    '''
    def rm(self):
        run_command_with_check([
            globals.docker_executable, 'rm', '-f', self.name
        ])
        

    '''    
    Check if the host path of `cp` is legal
    '''
    @staticmethod
    def check_cp_host_path_(path: str):
        if path == '-':
            raise DockerRuntimeError('Streaming the file is not allowed.')
        colon_index = path.find(':')
        if colon_index != -1 and colon_index != 1:
            # The colon_index != 1 is for windows compat
            raise DockerRuntimeError('Host path with a container specifier is not allowed.')

 
    '''
    Copy file or directory into the container
    '''
    def push_file(self, host_path: str, container_path: str):
        self.check_cp_host_path_(host_path)
        run_command_with_check([
            globals.docker_executable, 'cp',
            host_path,
            self.name + ':' + container_path
        ])
    

    '''
    Copy file or directory from the container
    '''
    def pull_file(self, container_path: str, host_path: str):
        self.check_cp_host_path_(host_path)
        run_command_with_check([
            globals.docker_executable, 'cp',
            self.name + ':' + container_path,
            host_path
        ])
       
 
    '''
    Generate filename for temporary exchange file
    '''
    def __tmp_filename(self, temp_dir):
        s = '0123456789qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM'
        return os.path.join(temp_dir, self.name + '__tmp-' + ''.join([
            s[random.randrange(0, len(s))]
            for i in range(0, 16)
        ]))

 
    '''
    Read binary file from the container by using a temporary file
    
    This method may throw IO errors on top of Docker errors.
    
    Do not use unless necessary. If transferring a text file is needed, please prefer the shell interface.
    '''
    def read_binary_file_with_temp(self, container_path: str, temp_dir='/tmp/'):
        tmp_filename = self.__tmp_filename(temp_dir)
        try:
            self.pull_file(container_path, tmp_filename)
            if os.path.isdir(tmp_filename):
                shutil.rmtree(tmp_filename)
                raise DockerRuntimeError('The requested file `' + container_path + '` is a directory')
            result = open(tmp_filename, 'rb').read()
        finally:
            if os.path.exists(tmp_filename): os.remove(tmp_filename)
        return result
    
    
    '''
    Write binary data to some file in the container by using a temporary file
    
    This method may throw IO errors on top of Docker errors.
    
    Do not use unless necessary. If transferring a text file is needed, please prefer the shell interface.
    '''
    def write_binary_file_with_temp(self, container_path: str, data: bytes, temp_dir='/tmp/'):
        tmp_filename = self.__tmp_filename(temp_dir)
        try:
            open(tmp_filename, 'wb').write(data)
            self.push_file(tmp_filename, container_path)
        finally:
            if os.path.exists(tmp_filename): os.remove(tmp_filename)


    # TODO: Stream binary files directly using `docker cp` with host filename `-`?
    
    
    '''
    Open the shell interface to the container.
    
    You may have multiple open shells at the same time.
    '''
    def open_shell(self):
        pipe = pexpect.popen_spawn.PopenSpawn([
            globals.docker_executable, 'exec',
            '-it', '--env', 'TERM=vanilla',
            self.name, '/bin/bash'
        ], timeout=30, maxread=1024*1024*30, encoding='utf-8', codec_errors='ignore')
        try:
            pipe.expect(r'[\#\$] ')
            
            # ==== Command prompt setup ====
            top_level_ps1 = 'ShellInterface@' + self.name + '$ '
            # Disable echo
            pipe.sendline('stty -echo')
            pipe.expect(r'[\#\$] ')
            # Clear the prompt first
            pipe.sendline('PS1=""')
            # Prevent conda from changing the command prompt
            pipe.sendline('conda config --set changeps1 False')
            # Set our unique command prompt
            pipe.sendline(f'PS1="{top_level_ps1}"')
            
            # ==== Back to track ====
            # Expect the command prompt we have just set
            pipe.expect_exact(top_level_ps1)
        except pexpect.exceptions.TIMEOUT:
            pipe.kill(signal.SIGKILL)
            raise ShellTimeout('Timeout while initializing shell.')
        except pexpect.exceptions.EOF:
            pipe.kill(signal.SIGKILL)
            assert isinstance(pipe.before, str)
            raise ShellFailure('Failed to open shell:\n' + pipe.before)
        
        return ShellInterface(pipe, top_level_ps1)
            

'''
The interface to the shell inside Docker.

For stability, the shell must have a unique and constant command prompt. This is automatically set up if you open the shell using `ContainerInterface#open_shell`.

The shell will NOT be automatically closed on error, but if any error occurs, you should kill it and reopen a new shell.
'''
class ShellInterface:
    def __init__(self, pipe: pexpect.popen_spawn.PopenSpawn, prompt: str):
        self.pipe = pipe
        self.prompt = prompt
    
    
    '''
    Definitely convert a string to bash-safe quoted string. Also escapes control characters.
    '''
    @staticmethod
    def quote_string(s: str):
        s = s.replace("'", "'\"'\"'")
        for i in range(32):
            s = s.replace(chr(i), f"'$'\\{oct(i)[2:].zfill(3)}''")
        return "'" + s + "'"
    
    
    '''
    Convert command to string, if it is given in form of an array.
    '''
    @staticmethod
    def command_to_string(command: Union[str, list[str]]):
        if isinstance(command, list):
            return ' '.join(map(lambda s: ShellInterface.quote_string(s), command))
        return command
    
    
    '''
    Get to the last command prompt
    '''
    def __get_command_prompt(self):
        while True:
            after_text = self.pipe.after
            if not isinstance(after_text, str): break
            if after_text.find(self.prompt, len(self.prompt)) != -1: # if we may find a second prompt string
                self.pipe.expect_exact(self.prompt)
            else:
                break
    
    
    '''
    Send a command to the active shell prompt
    '''
    def __send_command(self, command: Union[str, list[str]]):
        command = self.command_to_string(command)
        self.pipe.sendline(command)
        n_newlines = len([c for c in command if c in '\r\n'])
        try:
            try:
                for i in range(n_newlines):
                    self.pipe.expect_exact('> ')
            except pexpect.exceptions.TIMEOUT:
                raise ShellTimeout('Timeout waiting for multiline prompt when sending command:\n' + command)
        except pexpect.exceptions.EOF:
            raise ShellFailure('Shell closed while sending command:\n' + command)
    
    
    '''
    Wait for next shell prompt
    '''
    def __wait_next_prompt(self, command: Union[str, list[str]]):
        command = self.command_to_string(command)
        try:
            try:
                self.pipe.expect_exact(self.prompt)  # Expect the next command prompt
            except pexpect.exceptions.TIMEOUT:
                raise ShellTimeout('Timeout waiting for next shell prompt when executing command:\n' + command)
            
        except pexpect.exceptions.EOF:
            raise ShellFailure('Shell closed while executing command:\n' + command)
    
    
    '''
    Run a command and wait for output text. Does not strip the text.
    '''
    def run_command_blocking(self, command: Union[str, list[str]], extra_inputs: list[str] = [], strip_final_newline: bool = True) -> str:
        self.__get_command_prompt()
        self.__send_command(command)
        for inp in extra_inputs:
            self.pipe.send(inp)
        self.__wait_next_prompt(command)
        
        before_text = self.pipe.before
        if not isinstance(before_text, str):
            raise ShellFailure('Failed to run shell command, the returned result is not a string.')
        
        before_text = before_text.replace('\r\n', '\n')  # The tty seems to transform LF into CRLF. I don't know why.
       
        if strip_final_newline and before_text[-1:] == '\n':
            return before_text[:-1]
        return before_text
    
    
    '''
    Echo text file into the container.
    
    This is NOT meant for transferring binary files or very large files.
    '''
    def echo_file_to_container(self, filename: str, content: str):
        # Cannot directly echo.
        # Hint: Nothing is printed with echo -n '-n', but ` -n` can be printed with echo -n "" '-n'.
        return self.run_command_blocking('echo -n "" ' + self.quote_string(content) + ' | tail -c +2 > ' + self.quote_string(filename))
    
    
    '''
    Cat text file from the container.
    
    This is NOT meant for transferring binary files or very large files.
    '''
    def cat_file_from_container(self, filename: str):
        return self.run_command_blocking('cat ' + self.quote_string(filename), strip_final_newline=False)
    
    
    # Close the shell
    def kill(self):
        self.pipe.kill(signal.SIGKILL)
