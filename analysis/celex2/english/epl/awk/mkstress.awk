# MKSTRESS.AWK

# EPL

# This script returns the stress pattern of a syllabified transcription with
# stress markers.

BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f mkstress.awk file LexField_file1\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = MakeStressPattern(LexInfo_1);
	  printf("%s\n",LexInfo_1);
	}
}

function MakeStressPattern(String)
{     
    gsub(/./,"&%",String);              # % is nowhere else used.
    nc = split(String,StringArray,"%"); # Put string in a array. (nc = NumChar)

    NewSyllable = 1;
    StressPattern = "";

    for (i=1;i<nc;i++) {                    # Last character isn't important.
        if (NewSyllable) {
            if (StringArray[i] == "'")      # Syllable with primary stress.
                StressPattern = StressPattern "1";
            else if (StringArray[i] == "\"") # Syllable with secondary stress.
                StressPattern = StressPattern "2";
            else                            # 'Normal' syllable.
                StressPattern = StressPattern "0";
            NewSyllable = 0;
        } else
            if (StringArray[i] == "-")      # Start of new syllable.
                NewSyllable = 1;
    }
    return(StressPattern);
}
