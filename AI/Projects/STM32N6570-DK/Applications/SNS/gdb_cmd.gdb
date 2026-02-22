# Connect to the GDB server
target remote 127.0.0.1:61234
load cubeIDE/FSBL/Debug/AI_SNS_FSBL.elf
add-symbol-file cubeIDE/FSBL/Debug/AI_SNS_FSBL.elf
tbreak *BOOT_Application
	commands
	add-symbol-file cubeIDE/AppliSecure/Debug/AI_SNS_AppliSecure.elf
	add-symbol-file cubeIDE/AppliNonSecure/Debug/AI_SNS_AppliNonSecure.elf
	end
continue
