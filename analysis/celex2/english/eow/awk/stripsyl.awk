# STRIPSYL.AWK

# EOW

# This script is not required for deriving the columns listed in the CELEX
# User Guide. It is merely given to show how to strip a word of all its 
# syllable markers without affecting anything else.

BEGIN {
	
	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f stripsyl.awk file1 LexField_file1\n"
		exit(-1)
	}

	FS="\\";

	while(getline < ARGV[1])
	{
		LexInfo_1 = $ARGV[2];
		LexInfo_1 = StripSyllableMarkers(LexInfo_1);
		printf("%s\n", LexInfo_1);
	}
}

function StripSyllableMarkers(String) {

	 gsub(/--/,"%",String);
	 gsub("-","",String);
	 gsub("%","-",String);
	 return String;
}
