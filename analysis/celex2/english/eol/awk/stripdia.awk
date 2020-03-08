# STRIPDIA.AWK

# EOL

# This script strips the orthographic representation of all its (already 
# split off) diacritics.

BEGIN {
	
	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f stripdia.awk file1 LexField_file1\n"
		exit(-1)
	}

	FS="\\";

	while(getline < ARGV[1])
	{
		LexInfo_1 = $ARGV[2];
		LexInfo_1 = StripDiacritics(LexInfo_1);
		printf("%s\n", LexInfo_1);
	}
}

function StripDiacritics(String) {  
	 gsub(/[\"]|[\#]|[\`]|[\^]|[\,]|[\~]|[@]/,"",String);
	 return String;  
}  
