# WSL Environment Check

## Goal
了解Linux基础命令
## Commands
1、pwd
2、whoami
3、uname -a
4、ls /
## Expected Results
1、输出当前路径
2、输出当前用户名
3、输出当前unix详情
4、输出根目录下的文件目录
## Actual Results
1、<redacted-path>
2、<linux-user>
3、Linux <hostname> 5.15.167.4-microsoft-standard-WSL2 #1 SMP Tue Nov 5 00:21:55 UTC 2024 x86_64 x86_64 x86_64 GNU/Linux
4、Docker  boot  etc   init  lib32  libx32      media  opt   root  sbin  srv  tmp  var        wslGkHelC  wslbannjC
bin     dev   home  lib   lib64  lost+found  mnt    proc  run   snap  sys  usr  wslAKGhnC  wslLiHPnC  wslopfFnC
## Diagnosis
1、第一次whoami因为没有先运行wsl命令导致返回windows身份，我是从命令开头的PS字符发现的
2、localhost代理警告表示在windows层的网络被代理，但是这个代理不能被带到linux虚拟机
## English Summary
In Linux, the pwd command is used to print the path of current working directory.
In Linux, uname -r is used to show the Linux kernel release.
