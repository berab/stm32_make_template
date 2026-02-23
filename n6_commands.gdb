# Add echo pretty print
define hook-echo
	echo \n*****\n** 
end

define hookpost-echo
	echo \n*****\n
end

# Restore a memory file (ihex)
define restoreMem
  echo Restoring $arg0
  restore $arg1
  echo Done restoring $arg0
end


# Connect to the GDB server
target remote 127.0.0.1:61234

# Load the elf file to the board
load AI/Projects/STM32N6570-DK/Applications/NPU_Validation/armgcc/build/N6-Nucleo/Project.elf

# Set temporary breakpoint, and attach commands to it
echo Finished User setup phase. Setting BPX at end of init...
tbreak main.c:137
	commands

	# When done, stop debugging and quit gdb
	detach
	quit
	end
continue

