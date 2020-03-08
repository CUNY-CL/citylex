# CNVNUM2V.AWK

# EML

# This script changes verbal subcategory labels back into a simple 'V' code.

BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f cnvnum2v.awk file LexField\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = ConvertVerbNumbersToV(LexInfo_1);
	  printf("%s\n",LexInfo_1);
	}
}

function ConvertVerbNumbersToV(String)
{
    gsub(/[0-9]/,"V",String);
    return(String);
}
