# Makefile Template for Apollo4 devices using ST-Link GDB Server and gdb-multiarch 
Device: Apollo4 Blue Lite EVB
## Make:
```bash
make clean all
```

## RUN ST-LINK GDB Server:
```bash
/opt/st/stm32cubeide_1.16.0/plugins/com.st.stm32cube.ide.mcu.externaltools.stlink-gdb-server.linux64_2.1.400.202404281720/tools/bin/ST-LINK_gdbserver -p 61234 -l 1 -d -s -cp /opt/st/stm32cubeide_1.16.0/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.linux64_2.1.400.202404281720/tools/bin -m 0 &
```

## Connect GDB to the Server (.gdbinit is autocreated):
```bash
gdb-multiarch
```
