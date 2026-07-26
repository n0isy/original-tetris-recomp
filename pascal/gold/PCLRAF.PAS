CONST
	PASCALDEVICE = 'SY:';  (* DEVICE FOR THE PASCAL.SAV *)
			       (* ustrojstwo dlq translqtora  *)
	PASIMPDEVICE = 'SY:';  (* DEVICE FOR PASIMP.SAV *)
			       (* ustrojstwo dlq optimizatora *)
	PASLIBDEVICE = 'SY:';  (* DEVICE FOR PASCAL.OBJ *)
			       (* ustrojstwo dlq ispoln.sistemy *)
	PASPRFDEVICE = 'SY:';  (* DEVICE FOR PASPRF.OBJ *)
			       (* ustrojstwo dlq modulq profilirowaniq *)
	DEBUGDEVICE  = 'SY:';  (* DEVICE FOR PDT(A,B,0-9).OBJ *)
			       (* ustrojstwo dlq modulej otlad~ika *)
	NAMELIB      ='PASCAL';(*  NAME FOR LIBRARY  *)
                               (* imq biblioteki ispoln. sistemy *)

(****************************************************************)
(*	PCL --- RAFOS PASCAL COMMAND LANGUAGE			*)
(*								*)
(*	    FOR PASCAL V1.2 ON RAFOS				*)
(*								*)
(*
(* THIS PROGRAM WILL ONLY WORK ON RAFOS.  IT CREATES THE INDIRECT
(* COMMAND FILE PASCAL.COM CONTAINING THE APPROPRIATE COMMANDS TO
(* COMPILE AND POSSIBLY RUN THE DESIRED PROGRAM.  WHEN PCL EXITS, THE
(* COMMAND FILE IS INITIATED AND THE DESIRED COMMANDS ARE EXECUTED.
(* THE COMMAND FORMAT IS THE SAME AS THE CSI FORMAT.  THE FIRST
(* OUTPUT FILE IS AN OPTIONAL NAME FOR THE OUTPUT FILES.  THE SECOND
(* OUTPUT FILE IS AN OPTIONAL LISTING FILE.  THERE CAN BE UP TO SIX
(* INPUT FILES, WHICH WILL BE COMPILED TOGETHER IN THE ORDER SPECIFIED.
(* IF THE OPTIONAL OUTPUT NAME IS NOT GIVEN, THEN THE NAME OF THE OUTPUT
(* WILL BE THE SAME AS THE INPUT.  THERE ARE ALSO SWITCHES TO CONTROL
(* THE TYPE OF COMPILATION.
(*
(* dannaq programma prednazna~ena dlq sozdaniq komandnogo fajla PASCAL.COM,
(* soderv. komandy monitora dlq wypolneniq translqcii programmy s qzyka
(* paskalx i, esli neobhodimo, dlq ee zapuska. posle zawer{eniq programmy
(* PCL, awtomati~eski zapuskaetsq komandnyj fajl, w kotorom sodervatsq
(* wse neobhodimye komandy. PCL ispolxzuet standartnu` komandnu` stroku
(* w formate CSI. perwyj wyhodnoj fajl sodervit imq dlq wseh wyhodnyh
(* fajlow (on qwlqetsq neobqzatelxnym). wtoroj wyhodnoj fajl qwlqetsq
(* neobqzatelxnym fajlom listinga. dopustimo ukazywatx do 6 whodnyh
(* fajlow, kotorye budut skompilirowany wmeste w tom porqdke, w kotorom
(* oni pere~isleny. esli wyhodnoj fajl ne ukazan, to dlq wyhodnogo
(* fajla budet ispolxzowatxsq imq perwogo whodnogo fajla.
(* w komandnoj stroke movno ispolxzowatx sled. kl`~i:
(*
(*	/C	COMPILE TO A .SAV FILE BUT DON'T RUN
(*		podgotowitx fajl w formate .SAV, no ne wypolnqtx ego
(*
(*	/D	USE THE DEBUGGER
(*		podgotowitx programmu s otlad~ikom
(*
(*	/E	EXTERNAL COMPILATION.  CREATE AN .OBJ FILE
(*		sozdatx fajl tipa .OBJ, soderv. wne{nie procedury
(*
(*	/F	USE SUBROUTINE CALLS RATHER THAN FIS INSTRUCTIONS
(*		ispolxzowatx wyzowy podprogramm, a ne instrukcii FIS
(*
(*	/G	GO AND RUN THE PROGRAM
(*		podgotowitx i wypolnitx programmu
(*
(*	/I	RUN THE POST-COMPILATION IMPROVER IMP
(*		wypolnitx optimizaci` programmy posle kompilqcii
(*
(*	/L	PRINT OUT THE LISTING FILE. (TO TT: IF NO FILE SPECIFIED)
(*		polu~itx listing programmy. (esli ne ukazan fajl, to na TT:)
(*
(*	/M	CREATE THE .MAC FILE AND STOP
(*		polu~itx tolxko fajl tipa .MAC
(*
(*	/N	DON'T PUT OUT A LISTING (DEFAULT IS ERRORS ONLY TO TT:)
(*		ne polu~atx listinga (po umol~ani` na TT: wywodqtsq o{ibki )
(*
(*	/O	CREATE A .OBJ FILE AND STOP
(*		polu~itx ob'ektnyj fajl
(*
(*	/P	USE THE PROFILER
(*		ispolxzowatx modulx polu~eniq profilq programmy
(*
(*	/Q	USE THE FAST MACRO (MACFST.SAV) FOR THE ASSEMBLY
(*		ispolxzowatx bystryj translqtor makro (MACFST.SAV)
(*
(*	/S	SOURCE LINES IN THE .MAC FILE OR SOURCE WITH THE DEBUGGER
(*		wkl`~itx w tekst na makro ishodnu` programmu w wide
(*		kommentariew ili dlq raboty otlad~ika
(*
(*	/X	DOUBLE PRECISION REALS
(*		ispolxzowatx peremennye tipa REAL s dwojnoj to~nostx`
(*
(*)

TYPE
	WORD = 0..65535;

	FILESPEC = RECORD
		DEV : WORD;
		NAME : ARRAY [1..2] OF WORD;
		EXT : WORD;
	 	   END;

	CSIAREA = RECORD
		OUTSPEC : FILESPEC;
		FILLI : INTEGER;
		SEPARATELISTSPEC : FILESPEC;
		FILL : ARRAY [1..6] OF INTEGER;
		INPSPEC : ARRAY [1..6] OF FILESPEC;
		  END;

VAR
	I : INTEGER;
	ZEROES : ARRAY [1..4] OF 0..0;
	SWTCOMPILE,SWTDEBUG,SWTEXTERNAL,SWTFASTREALS,SWTGO,SWTIMP,SWTLIST,
	  SWTMACRO,SWTNOLIST,SWTOBJECT,SWTPROFILE,SWTSOURCE,SWTDOUBLE,
	  SWTQUICK : BOOLEAN;
	OUTFILE, MACFILE, LISTFILE, SYMFILE, OBJFILE, SAVEFILE,
	  TTYFILE, NULLFILE, TMPFILE, SEPARATELISTFILE, INPUTLINE : STRING;
	INPUTFILE : ARRAY [1..6] OF STRING;
	LASTINPUTFILE : 0..6;
	SWITCHCHARS : SET OF 'A'..'Z';
	CMD : TEXT;
	CSIPTR : ^CSIAREA;
	BADCSI : BOOLEAN;

(* GETCOMMAND --- GETS A LINE OF INPUT AND DECODES IT USING THE CSI IN
(*		  SPECIAL MODE.  THE SWITCHES ARE PACKED INTO A SET.  THE
(* FILES ARE THEN DECODED FROM RAD50 TO BE PLACED INTO STRINGS.  ALL OTHER
(* CONSTANT FILE NAMES STORED AS STRINGS ARE ALSO SET-UP
(*
(* procedura s~itywaet whodnu` stroku i obrabatywaet, ispolxzuq CSISPC.
(* kl`~i upakowywa`tsq w mnovestwo (SET). posle |togo imena fajlow
(* perekodiru`tsq w RAD50 i zapomina`tsq w sootwetstw. stroki. podgotawliwa-
(* `tsq takve wse stroki, soderv. postoqnnye imena fajlow *)

PROCEDURE GETCOMMAND;
  TYPE
	CHARS15 = ARRAY [1..15] OF CHAR;
  VAR
	I : INTEGER;
	DKINRAD50 : WORD;
	EXTRASWITCHES, SLASH : STRING;
	INDIRECTFILE : TEXT;
	SPEC : FILESPEC;
	RAD50TEXT : ARRAY [0..39] OF CHAR;
	RAD50PLACE : ARRAY [1..3] OF WORD;


    PROCEDURE EXPAND( SPEC:FILESPEC; VAR STR:STRING );

	PROCEDURE ADDCHAR( C:CHAR );
	  BEGIN
	    WITH STR DO BEGIN LEN := LEN+1;  CH[LEN] := C; END;
	  END;

	PROCEDURE RAD50( VAL:INTEGER );
	  VAR  I:1..3;   C:CHAR;
	  BEGIN
	    FOR I := 1 TO 3 DO
	      BEGIN
		C := RAD50TEXT[VAL DIV RAD50PLACE[I]];
		VAL := VAL MOD RAD50PLACE[I];
		IF C<>' ' THEN ADDCHAR(C);
	      END;
	  END;

      BEGIN (* EXPAND *)
	CLEAR(STR);
	IF (SPEC.DEV<>0) AND (SPEC.DEV<>DKINRAD50) THEN
	     BEGIN RAD50(SPEC.DEV); ADDCHAR(':'); END;
	RAD50(SPEC.NAME[1]);    RAD50(SPEC.NAME[2]);
	IF SPEC.EXT<>0 THEN BEGIN ADDCHAR('.'); RAD50(SPEC.EXT); END;
      END;


    PROCEDURE STRING15( VAR STR:STRING;  CHARS:CHARS15 );
      VAR I:INTEGER;
      BEGIN
	CLEAR(STR);   I := 15;
	WHILE (I>1) AND (CHARS[I]=' ') DO I := I-1;
	STR.LEN := I;
	FOR I := 1 TO I DO STR.CH[I] := CHARS[I];
      END;


  BEGIN (* GETCOMMAND *)
    DKINRAD50 := ((ORD('D')-ORD('@'))*40+(ORD('K')-ORD('@')))*40;
    RAD50TEXT := ' ABCDEFGHIJKLMNOPQRSTUVWXYZ   0123456789';
    RAD50PLACE[1]:=40*40;  RAD50PLACE[2]:=40;  RAD50PLACE[3]:=1;
    FOR I := 1 TO 4 DO ZEROES[I]:=0;
    STRING15(SLASH,'/              ');
    REPEAT
     REPEAT
	BADCSI := TRUE;
(*$C	.MCALL	.GTLIN
	MOV	%5,%1
	ADD	#INPUTLINE+2,%1
	BIC	#^O10000,@#^O44		;NO LOWER CASE INPUT
	JSR	%7,LOWSTK		;STACK TO LOW MEM: PROTECT FROM USR
	.GTLIN	%1,#1$
	JSR	%7,HISTK
	BR	2$
1$:	.ASCIZ	'*'<128>
	.EVEN
2$:
*)
	SWITCHCHARS := [];
	I := 1;  WHILE INPUTLINE.CH[I]<>CHR(0) DO I:=I+1;  INPUTLINE.LEN:=I-1;
	IF I=1 THEN WRITELN ('PCL V1.2');
       UNTIL INPUTLINE.LEN<>0;
	IF INPUTLINE.CH[1]='@' THEN
	  BEGIN
	    I := SEARCH(INPUTLINE,SLASH,1);
	    IF I=0 THEN I:=LEN(INPUTLINE)+1;
	    SUBSTRING(EXTRASWITCHES,INPUTLINE,I,LEN(INPUTLINE)-I+1);
	    SUBSTRING(INPUTLINE,INPUTLINE,2,I-2);
	    RESET(INDIRECTFILE,INPUTLINE.CH,'.COM');
	    READSTRING(INDIRECTFILE,INPUTLINE);
	    CLOSE(INDIRECTFILE);
	    CONCATENATE(INPUTLINE,EXTRASWITCHES);
	  END;
	IF LEN(INPUTLINE)<>0 THEN
	  BEGIN
	    INPUTLINE.CH[INPUTLINE.LEN+1] := CHR(0);
(*$C	.MCALL	.CSISPC
	.GLOBL	RTAREA, LOWSTK, HISTK
	JSR	%7,LOWSTK		;STACK TO LOW MEM: PROTECT FROM USR
	CLRB	BADCSI(5)
	MOV	%5,%1
	ADD	#INPUTLINE+2,%1
	MOV	%5,%2
	ADD	#ZEROES,%2
	.CSISPC	#RTAREA,%2,%1		;GET AND SCAN INPUT
	ROLB	BADCSI(5)
	BNE	8$
	MOV	(6)+,%0			;GET SWITCH COUNT
	BEQ	8$

3$:	MOV	(6)+,%1			;PICK-UP AND DECODE NEXT SWITCH
	BPL	4$
	TST	(6)+
4$:	BIC	#^O177640,%1
	CMP	#'A,%1
	BHI	7$
	CMP	#'Z,%1
	BLO	7$
	SUB	#'A,%1
	MOV	#1,%3
	CLR	%2
	BR	6$

5$:	ASL	%3
	ROL	%2
6$:	DEC	%1
	BPL	5$

	BIS	%3,SWITCHCHARS(5)	;SET BITS IN 'SWITCHCHARS'
	BIS	%2,SWITCHCHARS+2(5)

7$:	DEC	%0			;ANY MORE SWITCHES ON THE STACK?
	BNE	3$			;YES

8$:	MOV	#RTAREA,CSIPTR(5)
	JSR	%7,HISTK
*)
	  END;
	IF BADCSI THEN WRITELN('?PCL-F-ILLEGAL COMMAND');
    UNTIL NOT BADCSI;
    CSIPTR^.OUTSPEC.EXT := 0;
    EXPAND(CSIPTR^.OUTSPEC,OUTFILE);
    EXPAND(CSIPTR^.SEPARATELISTSPEC,SEPARATELISTFILE);
    LASTINPUTFILE := 6;
    WITH CSIPTR^ DO
      WHILE (INPSPEC[LASTINPUTFILE].DEV=0) AND (INPSPEC[LASTINPUTFILE].EXT=0)
	  AND (INPSPEC[LASTINPUTFILE].NAME[1]=0) AND (LASTINPUTFILE>1) DO
	LASTINPUTFILE := LASTINPUTFILE-1;
    IF LEN(OUTFILE)=0 THEN
      BEGIN
	SPEC := CSIPTR^.INPSPEC[LASTINPUTFILE];
	SPEC.DEV:=0;   SPEC.EXT:=0;
	IF SPEC.NAME[1]=0 THEN
	    STRING15(OUTFILE,'PROG           ')
	  ELSE
	    EXPAND(SPEC,OUTFILE);
      END;
    FOR I := 1 TO LASTINPUTFILE DO EXPAND(CSIPTR^.INPSPEC[I],INPUTFILE[I]);
    CLEAR(NULLFILE);
    STRING15(TTYFILE,'TT:            ');
    STRING15(TMPFILE,'TEMP.TMP       ');
  END;

(* EXAMINESWITCHES --- THE SWITCHES ARE DECODED TO BOOLEAN VALUES.
(*		       THEN CHECKS ARE MADE TO DETERMINE WHAT
(* THE USER MEANT BY THE SWITCHES HE USED.  APPROPRIATE NAMES ARE
(* SELECTED FOR INPUT AND OUTPUT FILES.  WHERE POSSIBLE, TEMPERARY
(* FILES ARE USED.
(*
(* procedura perewodit kl`~i iz komandnoj stroki w logi~eskie peremennye.
(* posle |togo proizwoditsq prowerka, ~to net protiwore~ij w ukazannyh
(* kl`~ah. opredelq`tsq imena trebuemyh dlq raboty fajlow.
(* gde wozmovno ispolxzu`tsq wremennye fajly. *)

PROCEDURE EXAMINESWITCHES;

    PROCEDURE CHECKSWITCH( C:CHAR; VAR FLAG:BOOLEAN );
      BEGIN FLAG := (C IN SWITCHCHARS); END;

  BEGIN
    CHECKSWITCH('C',SWTCOMPILE);
    CHECKSWITCH('D',SWTDEBUG);
    CHECKSWITCH('E',SWTEXTERNAL);
    CHECKSWITCH('F',SWTFASTREALS);
    CHECKSWITCH('G',SWTGO);
    CHECKSWITCH('I',SWTIMP);
    CHECKSWITCH('L',SWTLIST);
    CHECKSWITCH('M',SWTMACRO);
    CHECKSWITCH('N',SWTNOLIST);
    CHECKSWITCH('O',SWTOBJECT);
    CHECKSWITCH('P',SWTPROFILE);
    CHECKSWITCH('Q',SWTQUICK);
    CHECKSWITCH('S',SWTSOURCE);
    CHECKSWITCH('X',SWTDOUBLE);

    IF SWTEXTERNAL THEN SWTOBJECT := TRUE;
    IF SWTPROFILE THEN SWTDEBUG:=TRUE;
    IF NOT (SWTMACRO OR SWTOBJECT OR SWTCOMPILE) THEN SWTGO := TRUE;
    IF SWTMACRO OR (SWTSOURCE AND NOT SWTDEBUG) THEN
	MACFILE:=OUTFILE ELSE MACFILE:=TMPFILE;
    IF SWTDEBUG AND SWTSOURCE THEN LISTFILE:=OUTFILE ELSE
      IF LEN(SEPARATELISTFILE)<>0 THEN LISTFILE := SEPARATELISTFILE ELSE
	IF SWTNOLIST THEN LISTFILE := NULLFILE ELSE
	  LISTFILE := TTYFILE;
    IF SWTDEBUG OR SWTPROFILE THEN SYMFILE:=OUTFILE ELSE SYMFILE:=NULLFILE;
    IF SWTOBJECT THEN OBJFILE:=OUTFILE ELSE OBJFILE:=TMPFILE;
    SAVEFILE := OUTFILE;
  END;


PROCEDURE SWITCH( C:CHAR; FLAG:BOOLEAN );
  BEGIN
    IF FLAG THEN WRITE(CMD,'/',C);
  END;

PROCEDURE EXECUTECMDFILE;
  VAR
	CMDLEN ORIGIN 510B : INTEGER;
	CMDTEXT ORIGIN 512B : ARRAY [1..12] OF CHAR;
	JSW ORIGIN 44B : INTEGER;
  BEGIN
    JSW := JSW OR 4000B;
    CMDTEXT := '@PASCAL.COM ';
    CMDLEN := 12;
    CMDTEXT[CMDLEN] := CHR(0);
(*$C	CLR	R0
	.MCALL	.EXIT
	.EXIT
*)
  END;

BEGIN (* MAIN *)
  GETCOMMAND;
  EXAMINESWITCHES;
  REWRITE(CMD,'PASCAL.COM');

(* RUN THE COMPILER *)

  WRITELN(CMD,'RUN ',PASCALDEVICE,'PASCAL');
  WRITESTRING(CMD,MACFILE);
  IF LEN(LISTFILE)+LEN(SYMFILE)<>0 THEN
    BEGIN
      WRITE(CMD,',');  WRITESTRING(CMD,LISTFILE);
      IF LEN(SYMFILE)<>0 THEN
	BEGIN WRITE(CMD,',');  WRITESTRING(CMD,SYMFILE); END;
    END;
  WRITE(CMD,'=');   WRITESTRING(CMD,INPUTFILE[1]);
  FOR I := 2 TO LASTINPUTFILE DO
    BEGIN WRITE(CMD,','); WRITESTRING(CMD,INPUTFILE[I]); END;
  SWITCH('D',SWTDEBUG);
  SWITCH('E',SWTEXTERNAL);
  SWITCH('F',SWTFASTREALS);
  SWITCH('S',SWTSOURCE);
  SWITCH('X',SWTDOUBLE);
  IF NOT (SWTLIST OR (SWTSOURCE AND SWTDEBUG))
    THEN WRITE(CMD,'/N');
  WRITELN(CMD);

(* RUN THE POST-COMPILER IMPROVER: PASIMP *)

  IF SWTIMP THEN
    BEGIN
      WRITELN(CMD,'RUN ',PASIMPDEVICE,'PASIMP');
      WRITESTRING(CMD,MACFILE); WRITE(CMD,'=');
      WRITESTRING(CMD,MACFILE); WRITELN(CMD);
    END;

(* RUN MACRO *)

  IF SWTGO OR SWTCOMPILE OR SWTOBJECT THEN
    BEGIN
      IF SWTQUICK THEN WRITELN(CMD,'RUN ',PASCALDEVICE,'MACFST')
		  ELSE WRITELN(CMD,'R MACRO');
      WRITESTRING(CMD,OBJFILE); WRITE(CMD,'='); WRITESTRING(CMD,MACFILE);
      WRITELN(CMD);  WRITELN(CMD,'^C');
    END;

(* RUN LINK *)

  IF SWTGO OR SWTCOMPILE THEN
    BEGIN
      WRITELN(CMD,'R LINK');
      WRITESTRING(CMD,SAVEFILE);  WRITE(CMD,'=');
      WRITESTRING(CMD,OBJFILE);  WRITE(CMD,',',PASLIBDEVICE,NAMELIB);
      IF SWTPROFILE OR NOT SWTDEBUG THEN
	  BEGIN
	    IF SWTPROFILE THEN WRITE(CMD,',',PASPRFDEVICE,'PASPRF');
	    WRITELN(CMD)
	  END
	ELSE
	  BEGIN
	    WRITELN(CMD,'/C');
	    WRITELN(CMD,DEBUGDEVICE,'PASA/O:1/C');
	    WRITELN(CMD,DEBUGDEVICE,'PASB/O:1/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS0/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS1/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS2/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS3/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS4/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS5/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS6/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS7/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS8/O:2/C');
	    WRITELN(CMD,DEBUGDEVICE,'PAS9/O:2');
	  END;
      WRITELN(CMD,'^C');
    END;

(* DELETE TEMP FILE *)

  IF SWTGO OR SWTCOMPILE OR SWTOBJECT
     THEN WRITELN (CMD, 'DELE/NOQ TEMP.TMP');

(* RUN THE USER'S PROGRAM *)

  IF SWTGO THEN
    BEGIN
      WRITE(CMD,'RUN ');  WRITESTRING(CMD,SAVEFILE);  WRITELN(CMD);
    END;

(* GO DO THE COMMAND FILE *)

  CLOSE(CMD);
  EXECUTECMDFILE;
END.
                                                                                                                                                                                                                                                                                                                                                                                               