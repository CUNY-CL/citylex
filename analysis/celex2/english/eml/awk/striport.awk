# STRIPORT.AWK

# EML

# This script generates a hierarchical, bracketed representation of all
# levels of analysis, with word class information, but without the morphemes
# themselves.

BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f striport.awk file LexField\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = StripOrthographicInformation(LexInfo_1);
	  printf("%s\n",LexInfo_1);
	}
}

function StripOrthographicInformation(String)
{
    gsub(/./,"&%",String);
    nc = split(String,Array,"%");   # Split string into an array of characters.

    String = "";                    # Clear 'return' String...

    for (i=0;i<nc;i++) {
        if (Array[i] == "(") {
            String = String Array[i];
            while ((Array[i+1] != ")") && (Array[i+1] != "("))
                i++;
        } else
            String = String Array[i];
    }
    return(String);
}

