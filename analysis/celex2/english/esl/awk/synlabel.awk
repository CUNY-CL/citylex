# SYNLABEL.AWK

# ESL

# This script returns the label representations for all syntactic category
# codes given in the User Guide, by converting the basic numeric codes 
# into their string equivalents. 

BEGIN {
       if (ARGC%2 == 1) {
                printf "Incorrect number of arguments! (%d)\n", ARGC-1
                printf "USAGE !!\n awk -f synlabel.awk file LexField_file1 CL\n"
                exit(-1)
	      }

       if (ARGC%2==0 && ARGV[3] !~ /^CL$/) {
                printf "Incorrect LabelField argument given\n"
                printf "USAGE !!\n awk -f synlabel.awk file LexField_file1 CL\n"
                exit(-1)
	      }

       FS="\\";
       OFS="\\";
       
       while (getline < ARGV[1]) {

              LexInfo_1 = $ARGV[2];
              Conversion = ARGV[3];       

              LexInfo_1 = CatNumbersToCatLabels(LexInfo_1);     
              print $1,$2,LexInfo_1;
	    }
     }

function CatNumbersToCatLabels(String) {

  CLArray[1] = "N";
  CLArray[2] = "A";   
  CLArray[3] = "NUM";   
  CLArray[4] = "V";   
  CLArray[5] = "ART";   
  CLArray[6] = "PRON";   
  CLArray[7] = "ADV";   
  CLArray[8] = "PREP";   
  CLArray[9] = "C";   
  CLArray[10] = "I";
  CLArray[11] = "SCON";
  CLArray[12] = "CCON";
  CLArray[13] = "LET";
  CLArray[14] = "ABB";   
  CLArray[15] = "TO";

  if (Conversion == "CL") {
      String = CLArray[String];
     }
   return (String);
}
