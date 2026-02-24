Project for doing a "validate" on CM55, without Neural-Art IP.

# Flow

## Generate

To generate proper files to be used for this project, `stedgeai` should be provided with a `.json` file for 
specifying the locations where it can allocate activations.
An example of such a file is provided along with this README file (mypool_N6.json)

Weights shall be exported by stedgeai into a binary file, and an absolute address for the weights should be 
specified.


```
stedgeai generate -m <model> --target stm32n6 --binary --address 0x71000000 --memory-pool ./mypool_N6.json
```

This will generate network* files in the output directory (c files, h files, report files and a .bin file).

## Load the target

CM55_loader can be used to ease deployment of the project on N6.

This script works in a similar way as the n6_loader script (the interfaces are similar, i.e. config.json is needed to 
provide the tool with local installation paths, and a deployment-specific json file is used to tune deployment
on CM55, with the `--cm55-loader-config <config_file.json>` option.

It will:
- copy files from the output directory of stedgeai
- flash the weights to external flash
- compile the project
- load the project on board
- exit

## Validate

After loading the target, it is then possible to perform a validation with stedgeai:

```
stedgeai validate -m <model> --target stm32n6 --mode target --desc serial:921600 --memory-pool ./mypool_N6.json 		# DON't FORGET THE memory-pool option !!
```
or
```
stedgeai validate -m <model> --target stm32n6 --mode target --val-json st_ai_outputs/network_c_info.json
```

# Known limitations

Limitations of the current flow include:
- Weights MUST be located in external flash (i.e >0x7000'0000 , < 0x7FFF'FFFF)
   - It is not possible to use weights in internal ram for now
- Activations locations are defined in the memory-pool file provided
   - The example does not include dtcm for example, which can be added (but, be careful to properly init it)
