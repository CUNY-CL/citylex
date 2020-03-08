# CNTMORPH.AWK

# EML

# This script calculates the number of morphemes the word can be analysed
# into at the deepest level, i.e. the number of terminal nodes. 


BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f cntmorph.awk file LexField\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = CountMorphemes(StripClassLabels(LexInfo_1));
	  printf("%s\n",LexInfo_1);
	}
}

function CountMorphemes(String)
{
    gsub(/./,"&%",String);
    nc = split(String,Array,"%");   # Split string into an array of characters.

    Morphemes = 0;
    MorphemeStart = 0;

    for (i=0;i<nc;i++) {
        if ((MorphemeStart) && (Array[i] == ")")) {
            Morphemes++;           # Found a morpheme...
            MorphemeStart = 0;
        } else {
            if (Array[i] == "(") {
                MorphemeStart = 1;  # A new starting point found?
            }
        }
    }
    return(Morphemes);
}

function StripClassLabels(String)
{
    gsub(/./,"&%",String);
    nc = split(String,Array,"%");   # Split string into an array of characters.

    String = "";                    # Clear 'return' String...

    for (i=0;i<nc;i++) {
        if (Array[i] == "[")
            while (Array[i] != "]")
                i++;
        else
            String = String Array[i];
    }
    return(String);
}

