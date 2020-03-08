# PHON.AWK

# EPL

# This script returns the plain phonemic transcription of the word, without
# any syllable or stress markers, in any of the formats (SAM-PA, CELEX, CPA)
# specified on the command line.

BEGIN {

        if (ARGC <= 2) {
                printf "insufficient number of arguments! (%d)\n", ARGC-1
                printf "USAGE !!\n awk -f phon.awk file LexField_file1 (SP|CX|CP)\n"
                exit(-1)
	      }

        if (ARGC == 4 && ARGV[3] !~ /^(SP|CX|CP)$/) {
                printf "Incorrect 4th argument given\n"
                printf "USAGE !!\n awk -f phon.awk file LexField_file1 (SP|CX|CP)\n"
                exit(-1)
	      }

        FS="\\";

        while(getline < ARGV[1]){
	  LexInfo_1 = $ARGV[2];
          if (ARGV[3] != "") {
              Charset = ARGV[3];
          LexInfo_1 = ChangeRepresentation(AddFullStops(StripSyllableMarkers(StripStressMarkers(LexInfo_1))));
	    }
          else {
          LexInfo_1 = StripSyllableMarkers(StripStressMarkers(LexInfo_1));
	}
	  printf("%s\n",LexInfo_1);
        }
}


function AddFullStops(String)
{
    gsub(/./,"&.",String);      # Full stop after every character.
    return(String);
}


function StripStressMarkers(String)
{
    gsub("['\"]","",String);
    return(String);
}

function StripSyllableMarkers(String)
{
    WordMark = gsub(/--/,"%",String);   # Exchange with not-used character.
    gsub("-","",String);                # Remove all syllable markers.
    if (WordMark)
        gsub("%","-",String);           # Revive all normal hyphens.
    return(String);
}

function ChangeRepresentation(String) {
  gsub(/./,"&\034",String);
  nc = split(String,StringArray,"\034");
  String = "";

  SPArray["p"] = "p";
  SPArray["b"] = "b";
  SPArray["t"] = "t";
  SPArray["d"] = "d";
  SPArray["k"] = "k";
  SPArray["g"] = "g";
  SPArray["N"] = "N";
  SPArray["m"] = "m";
  SPArray["n"] = "n";
  SPArray["l"] = "l";
  SPArray["r"] = "r";
  SPArray["f"] = "f";
  SPArray["v"] = "v";
  SPArray["T"] = "T";
  SPArray["D"] = "D";
  SPArray["s"] = "s";
  SPArray["z"] = "z";
  SPArray["S"] = "S";
  SPArray["Z"] = "Z";
  SPArray["j"] = "j";
  SPArray["x"] = "x";
  SPArray["G"] = "G";
  SPArray["h"] = "h";
  SPArray["w"] = "w";
  SPArray["+"] = "pf";
  SPArray["="] = "ts";
  SPArray["J"] = "tS";
  SPArray["_"] = "dZ";
  SPArray["C"] = "N,";
  SPArray["F"] = "m,";
  SPArray["H"] = "n,";
  SPArray["P"] = "l,";
  SPArray["R"] = "r*";
  SPArray["i"] = "i:";
  SPArray["!"] = "i::";
  SPArray["#"] = "A:";
  SPArray["a"] = "a:";
  SPArray["$"] = "O:";
  SPArray["u"] = "u:";
  SPArray["3"] = "3:";
  SPArray["y"] = "y:";
  SPArray["("] = "y::";
  SPArray[")"] = "E:";
  SPArray["*"] = "/:";
  SPArray["<"] = "Q:";
  SPArray["e"] = "e:";
  SPArray["|"] = "|:";
  SPArray["o"] = "o:";
  SPArray["1"] = "eI";
  SPArray["2"] = "aI";
  SPArray["4"] = "OI";
  SPArray["5"] = "@U";
  SPArray["6"] = "aU";
  SPArray["7"] = "I@";
  SPArray["8"] = "E@";
  SPArray["9"] = "U@";
  SPArray["K"] = "EI";
  SPArray["L"] = "/I";
  SPArray["M"] = "Au";
  SPArray["W"] = "ai";
  SPArray["B"] = "au";
  SPArray["X"] = "Oy";
  SPArray["I"] = "I";
  SPArray["Y"] = "Y";
  SPArray["E"] = "E";
  SPArray["/"] = "/";
  SPArray["{"] = "{";
  SPArray["&"] = "a";
  SPArray["A"] = "A";
  SPArray["Q"] = "Q";
  SPArray["V"] = "V";
  SPArray["O"] = "O";
  SPArray["U"] = "U";
  SPArray["}"] = "}";
  SPArray["@"] = "@";
  SPArray["^"] = "/~:";
  SPArray["c"] = "{~";
  SPArray["q"] = "A~:";
  SPArray["0"] = "{~:";
  SPArray["~"] = "O~:";
  SPArray["-"] = "-";
  SPArray["'"] = "\"";
  SPArray["\""] = "%";
  SPArray["."] = ".";

  CXArray["p"] = "p";
  CXArray["b"] = "b";
  CXArray["t"] = "t";
  CXArray["d"] = "d";
  CXArray["k"] = "k";
  CXArray["g"] = "g";
  CXArray["N"] = "N";
  CXArray["m"] = "m";
  CXArray["n"] = "n";
  CXArray["l"] = "l";
  CXArray["r"] = "r";
  CXArray["f"] = "f";
  CXArray["v"] = "v";
  CXArray["T"] = "T";
  CXArray["D"] = "D";
  CXArray["s"] = "s";
  CXArray["z"] = "z";
  CXArray["S"] = "S";
  CXArray["Z"] = "Z";
  CXArray["j"] = "j";
  CXArray["x"] = "x";
  CXArray["G"] = "G";
  CXArray["h"] = "h";
  CXArray["w"] = "w";
  CXArray["+"] = "pf";
  CXArray["="] = "ts";
  CXArray["J"] = "tS";
  CXArray["_"] = "dZ";
  CXArray["C"] = "N,";
  CXArray["F"] = "m,";
  CXArray["H"] = "n,";
  CXArray["P"] = "l,";
  CXArray["R"] = "r*";
  CXArray["i"] = "i:";
  CXArray["!"] = "i::";
  CXArray["#"] = "A:";
  CXArray["a"] = "a:";
  CXArray["$"] = "O:";
  CXArray["u"] = "u:";
  CXArray["3"] = "3:";
  CXArray["y"] = "y:";
  CXArray["("] = "y::";
  CXArray[")"] = "E:";
  CXArray["*"] = "U:";
  CXArray["<"] = "O:";
  CXArray["e"] = "e:";
  CXArray["|"] = "&:";
  CXArray["o"] = "o:";
  CXArray["1"] = "eI";
  CXArray["2"] = "aI";
  CXArray["4"] = "OI";
  CXArray["5"] = "@U";
  CXArray["6"] = "aU";
  CXArray["7"] = "I@";
  CXArray["8"] = "E@";
  CXArray["9"] = "U@";
  CXArray["K"] = "EI";
  CXArray["L"] = "UI";
  CXArray["M"] = "AU";
  CXArray["W"] = "ai";
  CXArray["B"] = "au";
  CXArray["X"] = "Oy";
  CXArray["I"] = "I";
  CXArray["Y"] = "Y";
  CXArray["E"] = "E";
  CXArray["/"] = "Q";
  CXArray["{"] = "&";
  CXArray["&"] = "a";
  CXArray["A"] = "A";
  CXArray["Q"] = "O";
  CXArray["V"] = "V";
  CXArray["O"] = "O";
  CXArray["U"] = "U";
  CXArray["}"] = "U";
  CXArray["@"] = "@";
  CXArray["^"] = "Q~:";
  CXArray["c"] = "&~";
  CXArray["q"] = "A~:";
  CXArray["0"] = "&~:";
  CXArray["~"] = "O~:";
  CXArray["-"] = "-";
  CXArray["'"] = "'";
  CXArray["\""] = "\"";
  CXArray["."] = ".";

  CPArray["p"] = "p";
  CPArray["b"] = "b";
  CPArray["t"] = "t";
  CPArray["d"] = "d";
  CPArray["k"] = "k";
  CPArray["g"] = "g";
  CPArray["N"] = "N";
  CPArray["m"] = "m";
  CPArray["n"] = "n";
  CPArray["l"] = "l";
  CPArray["r"] = "r";
  CPArray["f"] = "f";
  CPArray["v"] = "v";
  CPArray["T"] = "T";
  CPArray["D"] = "D";
  CPArray["s"] = "s";
  CPArray["z"] = "z";
  CPArray["S"] = "S";
  CPArray["Z"] = "Z";
  CPArray["j"] = "j";
  CPArray["x"] = "x";
  CPArray["G"] = "G";
  CPArray["h"] = "h";
  CPArray["w"] = "w";
  CPArray["+"] = "pf";
  CPArray["="] = "C/";
  CPArray["J"] = "T/";
  CPArray["_"] = "J/";
  CPArray["C"] = "N,";
  CPArray["F"] = "m,";
  CPArray["H"] = "n,";
  CPArray["P"] = "l,";
  CPArray["R"] = "r*";
  CPArray["i"] = "i:";
  CPArray["!"] = "i::";
  CPArray["#"] = "A:";
  CPArray["a"] = "a:";
  CPArray["$"] = "O:";
  CPArray["u"] = "u:";
  CPArray["3"] = "@:";
  CPArray["y"] = "y:";
  CPArray["("] = "y::";
  CPArray[")"] = "E:";
  CPArray["*"] = "Q:";
  CPArray["<"] = "o:";
  CPArray["e"] = "e:";
  CPArray["|"] = "q:";
  CPArray["o"] = "o:";
  CPArray["1"] = "e/";
  CPArray["2"] = "a/";
  CPArray["4"] = "o/";
  CPArray["5"] = "O/";
  CPArray["6"] = "A/";
  CPArray["7"] = "I/";
  CPArray["8"] = "E/";
  CPArray["9"] = "U/";
  CPArray["K"] = "y/";
  CPArray["L"] = "q/";
  CPArray["M"] = "A/";
  CPArray["W"] = "a/";
  CPArray["B"] = "A/";
  CPArray["X"] = "o/";
  CPArray["I"] = "I";
  CPArray["Y"] = "Y";
  CPArray["E"] = "E";
  CPArray["/"] = "Q";
  CPArray["{"] = "^/";
  CPArray["&"] = "a";
  CPArray["A"] = "A";
  CPArray["Q"] = "O";
  CPArray["V"] = "^";
  CPArray["O"] = "O";
  CPArray["U"] = "U";
  CPArray["}"] = "Y/";
  CPArray["@"] = "@";
  CPArray["^"] = "Q~:";
  CPArray["c"] = "^/~";
  CPArray["q"] = "A~:";
  CPArray["0"] = "~/~:";
  CPArray["~"] = "O~:";
  CPArray["-"] = ".";
  CPArray["'"] = "'";
  CPArray["\""] = "\"";
  CPArray["."] = ".";
  
  if (Charset == "SP") {
       for (i=1; i <= nc; i++) {
            StringArray[i] = SPArray[StringArray[i]];
            String = String StringArray[i];
           }
       } 
  if (Charset == "CX") {
       for (i=1; i <= nc; i++) {
            StringArray[i] = CXArray[StringArray[i]];
            String = String StringArray[i];
           }
       } 
  if (Charset == "CP") {
       for (i=1; i <= nc; i++) {
            StringArray[i] = CPArray[StringArray[i]];
            String = String StringArray[i];
           }
       } 
   return (String);
}
