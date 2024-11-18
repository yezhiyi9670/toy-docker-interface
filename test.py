from docker_interface import *

if __name__ == '__main__':
    container = create_container_from_image(random_container_name(), 'continuumio/miniconda3')
    container.start()
    
    try:
        # container = ContainerInterface('swe-workspace-to09CC8cd8apDSmoOn2EFduu')
        shell = container.open_shell()
        
        container.push_file(__file__, '/root/test.py')
        
        # Run commands
        print(shell.run_command_blocking('echo 114514'))
        print(shell.run_command_blocking('pwd'))
        print(shell.run_command_blocking('ls'))
        print(shell.run_command_blocking('cat /root/test.py'))
        print(shell.run_command_blocking('cat /root/test.py > /root/test-copy.py'))
        
        open('retrieved_file_cat.txt', 'w').write(
            shell.run_command_blocking('cat /root/test.py')
        )
        open('retrieved_file_tmp.txt', 'wb').write(
            container.read_binary_file_with_temp('/root/test-copy.py')
        )
        
        print(shell.run_command_blocking(['echo', '14@3214###\'$$$\n2r31eqwr99*@#$*@$*$\r\nAAAAAA\rBBB']))
        print(shell.run_command_blocking('echo $?'))
        print(shell.run_command_blocking('non-existent-1145141919810'))
        
        # File transfer
        print(shell.echo_file_to_container('test.txt', 'Hello, wor\'\'$$l##d!\r\nGoodbye, w@@&#$*()*#!!!:}|{}>?<orld!\rEvil'))
        print(shell.cat_file_from_container('test.txt'))
        print(container.read_binary_file_with_temp('/test.txt'))
        print(container.write_binary_file_with_temp('/test.txt', '\x04\x03锟斤拷烫烫烫'.encode('utf-8')))
        print(container.read_binary_file_with_temp('/test.txt'))
        
        try:
            container.read_binary_file_with_temp('/etc')
        except Exception as e:
            print(repr(e))
    finally:
        container.kill()
        container.rm()
