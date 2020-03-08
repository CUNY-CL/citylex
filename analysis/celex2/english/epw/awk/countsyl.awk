# COUNTSYL.AWK

# EPW

# This script counts all phonetic syllables in a word, and returns the number
# of syllables found.

BEGIN {

        if (ARGC != 3) {
                printf "insufficient number of arguments! (%d)\n", ARGC-1
                printf "USAGE !!\n awk -f countsyl.awk file LexField"
                exit(-1)
	      }

        FS="\\";
        while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
          LexInfo_1 = CountSyllables(StripStressMarkers(LexInfo_1));
	  printf("%d\n",LexInfo_1);
        }
}

function StripStressMarkers(String)
{
    gsub("['\"]","",String);
    return(String);
}

function CountSyllables(String)
{
    if (String == "")
        return(0);
    else
        return(gsub(/-/,"",String) + 1);
}




