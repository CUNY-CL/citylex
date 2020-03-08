# CNTLEVEL.AWK

# EML

# This script calculates the number of levels at which immediate analysis can
# take place between the unanalysed word and the word fully analysed into 
# morphemes (including the top and bottom levels).

BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f cntlevel.awk file LexField\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = CountLevels(StripClassLabels(LexInfo_1));
	  printf("%s\n",LexInfo_1);
	}
}

function CountLevels(String)
{
    MaxLevels = 0;
    Levels = 0;

    gsub(/./,"&%",String);
    nc = split(String,Array,"%");   # Split string into an array of characters.

    for (i=0;i<nc;i++) {
        if (Array[i] == "(") {
            Levels++;
            if (Levels > MaxLevels)
                MaxLevels = Levels;
        } else {
            if (Array[i] == ")") {
                Levels--;
            }
        }
    }

    return(MaxLevels);
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

