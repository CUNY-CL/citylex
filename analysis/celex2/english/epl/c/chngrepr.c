/* ----------------------------------------------------------------------- *
 *                                                                         *
 *      CHNGREPR.C                                                         *
 *                                                                         *
 * CHNGREPR can be used to convert a field which contains a                *
 * DISC-representation of the phonetic transcription of a lemma            *
 * to one of the three other representations.                              *
 *                                                                         *
 * What happens when a line in the inputfile is longer than MAXLINE (2048) *
 * is undefined! :-)                                                       *
 *                                                                         *
 * Hedderik van Rijn, 930530, Original Version.                            *
 *                  , 930617, Added support for more than one convertion   *
 *                            in a single call to CHNGREPR.                *
 *					, 930803, Changed Phonectic Character Sets to support  *
 *                            English Phonetic Sets.                       *
 *                                                                         *
 * ----------------------------------------------------------------------- */

#include "stdio.h"
#include "stdlib.h"
#include "string.h"

/* -[ General Defines ]--------------------------------------------------- */

typedef unsigned int UINT;

#define FALSE       0
#define TRUE        (!FALSE)

/* -[CHNGREPR-specific Defines ]------------------------------------------ */

#define CHARACTERS		54

#define MAXLINE     	2048

#define NOERROR     	0
#define ARGSERROR   	1
#define MEMERROR    	2

#define NOCONVERTION	0
#define SP          	1
#define CX          	2
#define CP          	3

/* -[ Global Vars ]------------------------------------------------------- */

char    Mapped[5];      /* Contains last mapping done. */

char    DISC[CHARACTERS] =
				{ 'p', 'b', 't', 'd', 'k', 'g', 'N', 'm', 'n', 'l',
				  'r', 'f', 'v', 'T', 'D', 's', 'z', 'S', 'Z', 'j',
				  'x', 'h', 'w', 'J', '_', 'C', 'F', 'H', 'P', 'R',
				  'I', 'E', '{', 'V', 'Q', 'U', '@', 'i', '#', '$',
				  'u', '3', '1', '2', '4', '5', '6', '7', '8', '9',
				  'c', 'q', '0', '~' };

char   *Mapping[4][CHARACTERS] =
			{
				{ "",  "",  "",  "",   "",   "",   "",   "",   "",   "",
				  "",  "",  "",  "",   "",   "",   "",   "",   "",   "",
				  "",  "",  "",  "",   "",   "",   "",   "",   "",   "" },
	  /* SP */  { "p",  "b",   "t",   "d",  "k",  "g",  "N",  "m",  "n",  "l",
				  "r",  "f",   "v",   "T",  "D",  "s",  "z",  "S",  "Z",  "j",
				  "x",  "h",   "w",   "tS", "dZ", "N,", "m,", "n,", "l,", "r*",
				  "I",  "E",   "{",   "V",  "Q",  "U",  "@",  "i:", "A:", "O:",
				  "u:", "3:",  "eI",  "aI", "OI", "@U", "aU", "I@", "E@", "U@",
				  "{~", "A~:", "{~:", "O~:"  },
	  /* CX */  { "p",  "b",   "t",   "d",  "k",  "g",  "N",  "m",  "n",  "l",
				  "r",  "f",   "v",   "T",  "D",  "s",  "z",  "S",  "Z",  "j",
				  "x",  "h",   "w",   "tS", "dZ", "N,", "m,", "n,", "l,", "r*",
				  "I",  "E",   "&",   "V",  "O",  "U",  "@",  "i:", "A:", "O:",
				  "u:", "3:",  "eI",  "aI", "OI", "@U", "aU", "I@", "E@", "U@",
				  "&~", "A~:", "&~:", "O~:" },
	  /* CP */  { "p",   "b",   "t",    "d",  "k",  "g",  "N",  "m",  "n",  "l",
				  "r",   "f",   "v",    "T",  "D",  "s",  "z",  "S",  "Z",  "j",
				  "x",   "h",   "w",    "T/", "J/", "N,", "m,", "n,", "l,", "r*",
				  "I",   "E",   "^/",   "^",  "O",  "U",  "@",  "i:", "A:", "O:",
				  "u:",  "@:",  "e/",   "a/", "o/", "O/", "A/", "I/", "E/", "U/",
				  "^/~", "A~:", "^/~:", "O~:" }
			};

struct MapStruct_t {
	int FieldNo;
	char ConvertTo;
};

typedef struct MapStruct_t MapStruct;

MapStruct 	ToBeMapped[10];
int 		NumOfFieldsToMap;

/* -[ Functions ]--------------------------------------------[ ReadLine ]- */

char *ReadLine(FILE *inFile, char *retStr)
{
    char *ptr;

    char endOfLine = FALSE;
    char endOfFile = FALSE;

    if (!retStr)                /* Maybe we have to allocate mem for storage. */
        retStr = (char *)calloc(1,MAXLINE);

    memset(retStr,0,MAXLINE);   /* Erase all previous contenst of retStr. */

    if (retStr) {
        ptr = retStr;
        while (!endOfLine && !endOfFile) {
            if ((endOfFile = ( (fread(ptr,1,1,inFile)) ? FALSE : TRUE) ) == FALSE)
                endOfLine = (*ptr++ == '\n');
        }
    } else {
        printf("Error: Not enough memory!\n");
        exit(MEMERROR);
    }

        /* If nothing is read in, and we're at the end of the file,
           return NULL.                                             */

    if (endOfFile && (retStr[0] == '\0')) {
        free(retStr);
        retStr = NULL;
    } else
        if (endOfFile)          /* Something is read in, but no EOL */
            *(ptr++) = '\n';    /* mark... Add it ourselfs.         */

    return(retStr);
}

/* -------------------------------------------------------------[ MapTo ]- */

char *MapTo(char DISCch, UINT repr)
{
    UINT i;

    Mapped[0] = '\0';

	for (i=0;i<CHARACTERS;i++)
		if (DISC[i] == DISCch) {
			strcpy(Mapped,Mapping[repr][i]);
			return(Mapped);         /* Return immidiately. */
		}

    if (!Mapped[0]) {
        Mapped[0] = DISCch;
        Mapped[1] = '\0';
    }

    return(Mapped);
}

/* --------------------------------------------------------[ HelpScreen ]- */

void HelpScreen(int errNum)
{
	puts("Usage: CHNGREPR <File> <Representation> <Field> [<Repr> <Field>...]");
	puts("");
	puts("CHNGREPR can be used to convert field which contains a DISC-representation");
	puts("to another phonologic representation.");
	puts("");
	puts(" Arguments:");
	puts("");
	puts(" <File>            : CD-Celex file.");
	puts(" <Representation>  : Name of IPA-Representation to convert to.");
	puts("                     One of:");
	puts("                       SP : SAM-PA");
	puts("                       CX : CELEX");
	puts("                       CP : CPA");
	puts(" <Field>           : Number of column in <File> which contains");
	puts("                     DISC-representation. First column is 1.");
	puts("                     (Fields must be seperated by a '\\'.)");
	puts("");
	puts(" (There is a maximum of 10 pairs of Representations and Fields that CHNGREPR can");
	puts("  convert in one call.)");
	exit(errNum);
}

/* ---------------------------------------------------[ NeedsToBeMapped ]- */

int NeedsToBeMapped(int fieldNo)
{
	int i;

	for (i=0;i<NumOfFieldsToMap;i++) {
		if (ToBeMapped[i].FieldNo == fieldNo)
			return(ToBeMapped[i].ConvertTo);
	}
	return(FALSE);
}

/* --------------------------------------------------[ ProcessArguments ]- */

void ProcessArguments(int argc, char *argv[])
{
	int 	i;
	char 	convertTo;
	int 	wantedField;

	NumOfFieldsToMap = 0;


	if (argc < 4)
		HelpScreen(ARGSERROR);      /* Display help, exit with errorcode */

	for (i=0;(i<(argc-2)) && (i<20);i+=2) {
		if (strcmp(argv[2+i],"SP"))       /* Representation to convert to... */
			if (strcmp(argv[2+i],"CX"))
				if (strcmp(argv[2+i],"CP"))   {
					printf("Error: Representation to convert to needs to be one of 'SP', 'CX' or 'CP'.\n\n");
					HelpScreen(ARGSERROR);
				} else convertTo = CP;
			else convertTo = CX;
		else convertTo = SP;
										/* Field to convert... */
		if ((wantedField = atoi(argv[3+i])) == 0) {
			printf("Error: <Field> can't be: %s.\n",argv[3+i]);
			HelpScreen(ARGSERROR);
		}
		ToBeMapped[NumOfFieldsToMap].FieldNo = wantedField-1;
		ToBeMapped[NumOfFieldsToMap++].ConvertTo = convertTo;
	}
}


/* -[ Body ]-----------------------------------------------------[ main ]- */

int main(int argc, char *argv[])
{
    FILE *inFile;                   /* Inputfile Handle. */
    char *actLine = NULL;           /* Last line read. */
    char *ptr;                      /* Used when processing read line. */
    UINT  fieldNo;                  /* Current field. */
	UINT  convertTo;                /* Representation to convert to. */

	ProcessArguments(argc,argv);

				/* Open input file. -------------------------------------- */

    if ((inFile = fopen(argv[1],"rb")) == NULL) {
        printf("Error: Couldn't open input-file: %s \n",argv[2]);
        exit(ARGSERROR);
    }

                /* Read & process all lines in file. --------------------- */

    while ((actLine = (char *)ReadLine(inFile,actLine)) != NULL) {
        ptr = actLine;
        fieldNo = 0;
        do  {
            if (*ptr == '\\') {     /* Next field found! */
                fieldNo++;
                printf("%c",*ptr++);
            } else                  /* Necessary to map? */
				if (convertTo = NeedsToBeMapped(fieldNo)) {
                    printf("%s",MapTo(*ptr++,convertTo));
                } else
                    printf("%c",*ptr++);
        } while (*ptr != '\n');
        printf("\n");
    }

    return(NOERROR);                /* Exit with 'errorcode' 0... */
}

/* ----------------------------------------------------------------------- */
