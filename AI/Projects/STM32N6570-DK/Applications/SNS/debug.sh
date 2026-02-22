PATH_TO_CUBEIDE=~/PATH_TO/STM32CubeIDE
GDB_S=${PATH_TO_CUBEIDE}/plugins/com.st.stm32cube.ide.mcu.externaltools.stlink-gdb-server.win32_2.1.100.202309131603/tools/bin/ST-LINK_gdbserver.exe
GDB=${PATH_TO_CUBEIDE}/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.11.3.rel1.win32_1.1.100.202309151323/tools/bin/arm-none-eabi-gdb.exe
CubeProg_P=~/PATH_TO_CUBPROG/bin/
CubeProg_Ex=STM32_Programmer_CLI.exe


${GDB_S} -d -f 240 --apid 1 -v -cp ${CubeProg_P} &
sleep 1
echo 
echo
X=$(cat <<EOF
echo ${GDB} --command=gdb_cmd.gdb
EOF
)
echo -e $X
