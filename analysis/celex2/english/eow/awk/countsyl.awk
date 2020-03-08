# COUNTSYL.AWK

# EOW

# This script can be used to count the number of syllables.

BEGIN {
	
  if (ARGC != 3) {
    printf "insufficient number of arguments! (%d)\n", ARGC-1
      printf "USAGE !!\n nawk -f countsyl.awk file1 LexField_file1\n"
	exit(-1)
  }

  FS="\\";

  while(getline < ARGV[1]){
    LexInfo_1 = $ARGV[2];
    LexInfo_1 = CountSyllables(LexInfo_1);
    printf("%s\n",LexInfo_1);
  }
}

function CountSyllables(String) {
  if (String != "")
    return gsub(/-[^-]/,"",String) + gsub(/[\ ]/,"",String) + 1;
  else
    return 0;
}
