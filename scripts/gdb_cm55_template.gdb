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

######### START OF SCRIPT ############
# Connect to the GDB server
target remote 127.0.0.1:61234

# Load the elf file to the board
load build/Project.elf

# Set temporary breakpoint, and attach commands to it
echo Finished User setup phase. Setting BPX at end of init...
tbreak main.c:##BREAKLINE##
	commands
## 	restoreMem ##RAMNAME## ##RAMFILE##
	# When done, stop debugging and quit gdb
	detach
	quit
	end
continue

