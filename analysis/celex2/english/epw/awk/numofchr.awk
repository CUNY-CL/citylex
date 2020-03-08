# NUMOFCHR.AWK

# EPW

#  This script simply counts all characters in a given string, and returns
#  the number of characters found.

BEGIN {

        if (ARGC != 3) {
                printf "insufficient number of arguments! (%d)\n", ARGC-1
                printf "USAGE !!\n awk -f numofchr.awk file LexField_file1\n"
                exit(-1)
	      }

        FS="\\";
        while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
          LexInfo_1 = NumOfChar(StripSyllableMarkers(StripStressMarkers(LexInfo_1)));
	  printf("%d\n",LexInfo_1);
        }
}


function NumOfChar(String)
{
    return(gsub(/./,"",String));
}


function StripSyllableMarkers(String)
{
    WordMark = gsub(/--/,"%",String);   # Exchange with not-used character.
    gsub("-","",String);                # Remove all syllable markers.
    if (WordMark)
        gsub("%","-",String);           # Revive all normal hyphens.
    return String;
}

function StripStressMarkers(String)
{
    gsub("['\"]","",String);
    return(String);
}
