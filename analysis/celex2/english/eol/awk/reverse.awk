# REVERSE.AWK

# EOL

# This script returns a reversed string after stripping away all (already
# split off) diacritics.

BEGIN {
	
	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f reverse.awk file1 LexField_file1\n"
		exit(-1)
	}

	FS="\\";

	while(getline < ARGV[1])
	{
		LexInfo_1 = $ARGV[2];
		LexInfo_1 = ReverseString(StripDiacritics(LexInfo_1));
		printf("%s\n",LexInfo_1);
	}
}


function ReverseString(String) {
	gsub(/[A-Z]|[a-z]|[\.]|[\ ]|[\/]|[\']|\-/,"&%",String); 
														# % is nowhere else used.
	nc = split(String,StringArray,"%");    # Put string in a array.
	String = "";
	for (i=(nc-1);i>0;i--) {                 # Reverse string
		String = String StringArray[i];
	}
	return String;
}

function StripDiacritics(String) {
         gsub(/[\"]|[\#]|[\`]|[\^]|[\,]|[\~]|[@]/,"",String);
         return String;
}
