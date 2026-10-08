#include <stdio.h>
#include <string.h>
#include "saf_archive.h"

int main(int argc, char *argv[])
{
    if (argc == 4 && !_stricmp(argv[1], "U")) return saf_unpack(argv[2], argv[3]);
    if (argc == 4 && !_stricmp(argv[1], "P")) return saf_pack(argv[2], argv[3]);
    printf("SAF0 recursive archive tool\n  %s U input.saf output_folder\n  %s P input_folder output.saf\n", argv[0], argv[0]);
    return 1;
}
