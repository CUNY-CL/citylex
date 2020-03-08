# COUNTCHR.AWK

# EOL

# This script calculates the number of characters in a string, ignoring
# split-off diacritics and any non-alphanumeric characters.

BEGIN{
  if(ARGC != 3){
    printf "insufficient number of arguments! (%d)\n", ARGC-1
      printf "USAGE !!\n awk -f countchr.awk file1 LexField_file1\n"
	exit(-1)
  }

  FS="\\";
# InitializeToLower(Map);

  while(getline < ARGV[1]){
    LexInfo_1 = $ARGV[2];
    LexInfo_1 = CntChr(ToLower(StripNonAlphabetics(StripDiacritics(LexInfo_1))));
    printf("%s\n",LexInfo_1);
  }
}

function InitializeToLower(Map) {
  caps="ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  lower="abcdefghijklmnopqrstuvwxyz";
  gsub(/[A-Z]/,"&%",caps);            # caps = "A-B-C-..-Z"
    gsub(/[a-z]/,"&%",lower);         # lower = "a-b-c-..-z"
      split(caps,Caps,"%");           # Caps becomes array
	split(lower,Lower,"%");
  for (i = 1; i <= 26; i++) {
    Map[Caps[i]] = Lower[i];          # Map is array with indexes 'A'..'Z'
  }                                   # and corresponding contents 'a'..'z'.
}

# ToLower is a function which converts a string to lowercase. Only the
# characters [A..Z] are converted, all other characters are ignored.

function ToLower(String){
  if(ToLowerInit==0){                              # First time initialisation.
    InitializeToLower(Map);
    ToLowerInit = 1;                                  # Variables are static.
  }
  gsub(/./,"&%",String);                              # % is used nowhere else.
    nf = split(String,StringArray,"%");               # Put string in a array.
      lowString = "";                                 # Variables are static.
	for(i = 1; i < nf; i++){                    # i < nf changed to i <= nf
	  if(StringArray[i]~/[A-Z]/) { 
	    lowString = lowString Map[StringArray[i]];# Remap
	  } 
	  else{
	    lowString = lowString StringArray[i];     # Just store
	  }
	}
  return(lowString);
}

function StripNonAlphabetics(String) {
	 gsub(/[^a-z|^A-Z]/,"",String);
	 return String;
}

function StripDiacritics(String) {  
	 gsub(/[\"]|[\#]|[\`]|[\^]|[\,]|[\~]|[@]/,"",String);
	 return String;  
}  

function CntChr(String) {  
	return(gsub(/[A-Z]|[a-z]/,"",String));  
}  


