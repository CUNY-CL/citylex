# CNTMC.AWK

# EML

# This script calculates the number of components the word can be analysed
# into at the immediate analysis level, i.e. the number of bases and 
# affixes at the first level of analysis. 

BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f cntmc.awk file LexField\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = CountMorpComponents(ConvertVerbNumbersToV(LexInfo_1));
	  printf("%s\n",LexInfo_1);
	}
}

function CountMorpComponents(String)
{
    if (String != "")
        return(length(String));
    else
        return(0);
}

function ConvertVerbNumbersToV(String)
{
    gsub(/[0-9]/,"V",String);
    return(String);
}

