# CONVBRAC.AWK

# EPL

# This script converts the CV-pattern transcription of a word with brackets
# into a hyphenated transcription.
# Note that ambisyllabic consonants, when taken out of the brackets
# surrounding them, appear twice (on both sides of the syllable boundary) in
# the hyphenated notation. 

BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f convbrac.awk file LexField_file1\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = ConvertBrackets(LexInfo_1);
	  printf("%s\n",LexInfo_1);
	}
}

function ConvertBrackets(String)
{
    AmbiSyllabic = 0;
    SyllabicLevel = 0;

    OldString = String;

    gsub(/./,"&%",String);              # % is nowhere else used.
    nc = split(String,StringArray,"%"); # Put string in a array. (nc = NumChar)

                # Determine if current word is ambisyllabic.

    for (i=1;((i<=nc)&&(!AmbiSyllabic));i++) {
        if ((StringArray[i] == "[") && (SyllabicLevel))
            AmbiSyllabic = 1;
        if (StringArray[i] == "[")
            SyllabicLevel++;
        else if (StringArray[i] == "]")
            SyllabicLevel--;
    }

    SyllabicLevel = 0;

    if (AmbiSyllabic) {
       String = "";
       for (i=1;i<=nc;i++) {
           if (StringArray[i] == "[") {
               SyllabicLevel++;
           }
           else if (StringArray[i] == "]") {
               SyllabicLevel--;
               if (StringArray[i+1] != "") 
                   String = String "-";
           }
           else
               if (SyllabicLevel > 1) {      # Ambisyl. Char. found.
                  String = String StringArray[i] "-" StringArray[i];
                  i++;
                  SyllabicLevel--;
               } else {
                  String = String StringArray[i];
               }
        }
     } else {
        gsub("\]\[","-",OldString);
        gsub(/\[|\]/,"",OldString);
	String = OldString;
     }

     return(String);
}
