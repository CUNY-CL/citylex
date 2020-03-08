# EXTRCTWC.AWK

# EML

# This script extracts word class and affix labels from the Structured 
# Segmentation.

BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f extrctwc.awk file LexField\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = ExtractWordClass(LexInfo_1);
	  printf("%s\n",LexInfo_1);
	}
}

function ExtractWordClass(String)
{
    gsub(/./,"&%",String);
    nc = split(String,Array,"%");   # Split string into an array of characters.

    String = "";                    # Clear 'return' String...

            # The next loop searches for the character starting a Word Class
            # Indicator (WCI), the character '['. When it is found, the
            # character two places further down is examined. If it is a WCI 
            # ending character (']'), we know this WCI isn't an affix, so we can
            # simply store the WCI in the return string. If the WCI occupies
            # more than 1 character, it is an affix. The next character
            # searched must be the one after the ']'.

            # Meanwhile, we're examining the structure of the input, so that
            # only the WCI we want (the WCI's connected to the morphemes)
            # are presented in the output.

    for (i=0;i<nc;i++) {
        if ((Array[i] == "[") &&    # Then: here begins WordClassIndicator.
            (Morpheme)) {           # Then: a morpheme we're looking for.

            if (Array[i+2]=="]") {  # Then: not an affix, simply copy.
                String = String Array[++i];
                i++;                # Go to character after the ']'.
            } else {                # Then: it's a affix.
                String = String "x";    # Store affix representation.
                i+=3;
                while (Array[i] != "]") # Go to character after the ']'.
                    i++;
           }
           Morpheme = 0;
        } else {
            if ((MorphemeStart) && (Array[i] == ")")) {
                Morpheme = 1;           # Found a morpheme...
                MorphemeStart = 0;
            } else {
                if (Array[i] == "(") {
                    Morpheme = 0;
                    MorphemeStart = 1;  # A new starting point found?
                }
            }
        }
    }
    return(String);
}


