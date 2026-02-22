PATH_TO_CUBE_PROG=~/PATH_TO_CUBE_PROG/bin
CubeProg=${PATH_TO_CUBE_PROG}/STM32_Programmer_CLI.exe
SignTool=${PATH_TO_CUBE_PROG}/STM32MP_SigningTool_CLI.exe
ExternalLoader_arg=${PATH_TO_CUBE_PROG}/ExternalLoader/MX66UW1G45G_STM32N6570-DK.stldr
IAR=0

set -x
if [[ $IAR -eq 1 ]]
then
	UsedP="** Using IAR Project"
	S_BIN=EWARM/App_Secure/STM32N6570-DK_Secure/Exe/Project.bin
	NS_BIN=EWARM/App_NonSecure/STM32N6570-DK_NonSecure/Exe/Project_ns.bin
else
	UsedP="** Using CubeIDE Project"
	S_BIN=cubeIDE/AppliSecure/Debug/AI_SNS_AppliSecure.bin
	NS_BIN=cubeIDE/AppliNonSecure/Debug/AI_SNS_AppliNonSecure.bin
fi

# Sign stuff
${SignTool} -bin ${S_BIN} -s -nk -of 0x80000000 -t fsbl -o Project_s-trusted.bin -hv 2.1 -dump Project_s-trusted.bin
${SignTool} -bin ${NS_BIN} -s -nk -of 0x80000000 -t fsbl -o Project_ns-trusted.bin -hv 2.1 -dump Project_ns-trusted.bin
# Program stuff
${CubeProg} -q -c port=SWD mode=powerdown ap=1
${CubeProg} -q -c port=SWD mode=hotplug ap=1 --extload ${ExternalLoader_arg} --download Project_s-trusted.bin 0x70100000
${CubeProg} -q -c port=SWD mode=hotplug ap=1 --extload ${ExternalLoader_arg} --download Project_ns-trusted.bin 0x70180000


set +x 
echo -e "${UsedP}"