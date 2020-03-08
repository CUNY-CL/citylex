# STRIPSTR.AWK

# EML

# This script generates a representation of all morphemes at the deepest
# level of analysis, without brackets indicating levels, and without word
# class information.


BEGIN {

	if (ARGC != 3) {
		printf "insufficient number of arguments! (%d)\n", ARGC-1
		printf "USAGE !!\n awk -f stripstr.awk file LexField\n"
		exit(-1)
	      }

	FS="\\";
	while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
	  LexInfo_1 = StripStructureMarkers(StripClassLabels(LexInfo_1));
	  printf("%s\n",LexInfo_1);
	}
}

function StripStructureMarkers(String)
{
    gsub(/[(]|[)]/,"",String);
    gsub(",","+",String);
    return(String);
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

