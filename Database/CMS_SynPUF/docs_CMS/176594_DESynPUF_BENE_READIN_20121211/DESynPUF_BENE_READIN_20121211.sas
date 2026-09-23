/*-------------------------------------------------------------------*/
/*  Program Name: DESYNPUF_BENE_READIN.SAS                           */
/*  SAS Version:  Tested under SAS 9.3 Windows XP                    */
/*  Purpose:      Create SAS data sets from BENE synthetic PUF CSV   */
/*                files. Each BENE CSV file contains beneficiary data*/
/*                for one year.                                      */
/*                                                                   */
/*  BACKGROUND:   Each data type in the CMS Linkable 2008-2010       */
/*  Medicare DE-SynPUFs was released in 20 separate subsamples. The  */
/*  same group of beneficiary IDs are in subsamples with the same    */
/*  number. The suffix of each CSV filename contains the subsample   */
/*  number. This design allows DE-SynPUFs users who do not need the  */
/*  entire synthetic population of DE-SynPUFs to read in only as many*/
/*  subsamples as they desire. This read-in program allows users to  */
/*  specify which Beneficiary subsamples to read in and to combine.  */
/*  A Beneficiary subsample contains three CSV files, one for each   */
/*  year (2008, 2009, 2010). All three annual CSV files in a         */
/*  subsample must be downloaded before processing this program.     */
/*                                                                   */
/*-------------------------------------------------------------------*/
/*  USER INSTRUCTIONS: Modify the following as necessary.            */
/*  1. Assign to macro variable INFILEPATH the path where the CSV    */
/*     files are stored.                                             */
/*  2. Assign to macro variables INFILENAME2008, INFILENAME2009, and */
/*     INFILENAME2010 the filenames of the CSV files for each year.  */
/*     Do not include the subsample number and the CSV extension. The*/
/*     program will add the subsample number and the CSV extension to*/
/*     the filename.                                                 */
/*  3. Specify path for DESYNPUF LIBNAME. This is the location where */
/*     the SAS data sets created by this program will be stored.     */
/*  4. Assign to macro variables OUTDSNAME2008, OUTDSNAME2009, and   */
/*     OUTDSNAME2010 the names of the SAS data sets created from the */
/*     CSV files. Do not include the subsample number. The program   */
/*     will add that as a suffix to your SAS data set names. The name*/
/*     must conform to SAS naming rules and be 30 charactersor less  */
/*     in length. The 30 characters limit allows for the addition of */
/*     the subsample number to the name.                             */
/*  5. Set parameters on calls to macro program DESYNPUF_BENE_READIN.*/
/*     Keep only the calls to macro program DESYNPUF_BENE_READIN for */
/*     the subsamples that you want to process. Comment out the calls*/
/*     to DESYNPUF_BENE_READIN for the subsamples that you do not    */
/*     want to process (or delete the calls).                        */
/*     This macro has two parameters and both are required:          */
/*     FILENUMBER= and SORTDS=.                                      */
/*     - Set the FILENUMBER= parameter value to the numeric suffix of*/
/*       the CSV files that you want to read in. A single subsample  */
/*       is separated into one CSV file per year (2008, 2009, 2010). */
/*       This macro program creates a data set from each CSV file.   */
/*       The FILENUMBER= value is the subsample number. The SAS data */
/*       sets that are created will have the same numeric suffix.    */
/*     - The SORTDS= parameter specifies whether you want to sort the*/
/*       new data sets by DESYNPUF_ID. The CSV files are saved in    */
/*       ASCII DESYNPUF_ID order and so you may not need to sort the */
/*       files if you intend to use them in ASCII DESYNPUF_ID order. */
/*  6. Optionally, call macro program DESYNPUF_BENE_COMBINE if you   */
/*     want to combine the new BENE data sets into one data set per  */
/*     year. This code requires that the data sets you want to       */
/*     combine are consecutively numbered subsamples.                */
/*       The name of the output data set created by this macro       */
/*     is the name specified by macro variable OUTDSNAME. No         */
/*     subsample numbers will be added as a suffix to the data set   */
/*     name.                                                         */
/*     NOTE: If you do not have consecutively numbered subsamples,   */
/*     you will need to write a DATA step that concatenates these    */
/*     subsample data sets.                                          */
/*       This code interleaves the data sets for a year by           */
/*     DESYNPUF_ID. Therefore, the data sets that you want to combine*/
/*     must be in order by DESYNPUF_ID. If you do not want to call   */
/*     macro program DESYNPUF_BENE_COMBINE, comment out (or delete)  */
/*     the call to this macro program.                               */
/*       This macro program has two parameters STARTNUMBER= and      */
/*     ENDNUMBER=. These parameters specify the numeric range of     */
/*     files (the subsample numbers) that you want to combine. All   */
/*     three years are processed and a data set is created for each  */
/*     year.                                                         */
/*       If you want to combine the data sets at a later time, you   */
/*     can run this macro program by itself. Do steps 1-4. Do not do */
/*     Step 5 and remove the calls to macro program                  */
/*     DESYNPUF_BENE_READIN. Depending on any post-processing that   */
/*     you may have done, you might need to sort the data sets that  */
/*     you want to combine by DESYNPUF_ID before you call            */
/*     DESYNPUF_BENE_COMBINE.                                        */
/*                                                                   */
/*-------------------------------------------------------------------*/
/*                                                                   */
/*  Date:         13 Nov 2012                                        */
/*  Last Updated: 11 Dec 2012 11:42:44ec 2012 11:39:19               */
/*-------------------------------------------------------------------*/

/*********************************************************************/
/* Declare global macro variables used by this program.              */
/*********************************************************************/
%symdel infilepath infilename2008 infilename2009 infilename2010
                   outdsname2008  outdsname2009 outdsname2010;
%global infilepath infilename2008 infilename2009 infilename2010
                   outdsname2008  outdsname2009 outdsname2010;

/*********************************************************************/
/* 1. Specify path of input CSV files. Do not enclose value in       */
/*    quotation marks.                                               */
/*********************************************************************/
%let infilepath= ;

/**************************************************************************/
/* 2. Specify first part of filename for input CSV files. Do not include  */
/*    the subsample number and do not include the CSV extension. The      */
/*    program assigns these values. Do not enclose the filenames in       */
/*    quotation marks. There is one macro variable per year.              */
/**************************************************************************/
%let infilename2008=DE1_0_2008_Beneficiary_Summary_File_Sample_;
%let infilename2009=DE1_0_2009_Beneficiary_Summary_File_Sample_;
%let infilename2010=DE1_0_2010_Beneficiary_Summary_File_Sample_;

/**************************************************/
/* 3. Specify LIBNAME of DE-SynPUF BENE files     */
/**************************************************/
libname desynpuf " ";

/**************************************************************************/
/* 4. Specify filenames(30 characters or less) of SAS datasets created by */
/*    this program. For Beneficiary data, a data set is created for each  */
/*    of the three years. Do not include the subsample number suffix. The */
/*    program adds that value to the end of the SAS data set name. There  */
/*    is one macro variable per year.                                     */
/**************************************************************************/
%let outdsname2008=DE1_0_2008_Bene_Sample_;
%let outdsname2009=DE1_0_2009_Bene_Sample_;
%let outdsname2010=DE1_0_2010_Bene_Sample_;

/**************************************************************************/
/* Set SAS options for this program:                                      */
/*   VALIDVARNAME=UPCASE: Ensure that all variable names are in uppercase.*/
/*   COMPRESS=BINARY: Compress data sets created by this program.         */
/*   MPRINT: View resolved code in SAS log (optional -- NOMPRINT turns it */
/*           off)                                                         */
/**************************************************************************/
options validvarname=upcase
        compress=binary
        mprint
        ls=100 ps=60;

/*********************************************************************************/
/*********************************************************************************/
/* START OF SECTION THAT SHOULD NOT BE MODIFIED                                  */
/*********************************************************************************/

%macro desynpuf_bene_readin(filenumber=,sortds=);
  %******************************************************************************;
  %* Macro program DESYNPUF_BENE_READIN creates a data set by reading a single   ;
  %* Synthetic PUF BENE subsample. The required FILENUMBER= parameter identifies ;
  %* which Beneficiary subsample to read in. Each subsample contains 3 CSV files,;
  %* one for each year.  The CSV files are stored with a numeric suffix, which is;
  %* the subsample number. If you want to read in multiple subsamples, you must  ;
  %* call DESYNPUF_BENE_READIN once for each subsample.                          ;
  %*                                                                             ;
  %* The required SORTDS= parameter can take values Y, YES, N, and NO. The value ;
  %* of SORTDS specifies whether the data sets that are created should be sorted ;
  %* by DESYNPUF_ID.                                                             ;
  %*                                                                             ;
  %* The input path and input filename are determined by the values of global    ;
  %* macro variables that are defined at the top of this program.                ;
  %*                                                                             ;
  %* The DESYNPUF libname and output data set name are determined by the values  ;
  %* of the global macro variables that are defined at the top of this program.  ;
  %*                                                                             ;
  %* See instructions at the top of this program for how to assign path and      ;
  %* filename values to the global macro variables.                              ;
  %*                                                                             ;
  %* After the new data set is created, output is generated using PROCs CONTENTS,;
  %* PRINT, MEANS, and FREQ to verify the data set contents.                     ;
  %******************************************************************************;

  %local startyear endyear y infilename outdsname;
  %let startyear=2008;
  %let endyear=2010;

  %let sortds=%upcase(&sortds);

  %do y=&startyear %to &endyear;
    %let infilename=&&infilename&y;
    %let outdsname=&&outdsname&y;
    filename inbene "&infilepath\&infilename&filenumber..csv" ;

    data desynpuf.&outdsname&filenumber(label="&infilename.&filenumber");
      infile inbene dsd dlm=',' lrecl=500 firstobs=2 stopover;

      attrib DESYNPUF_ID     length=$16 format=$16.       label='DESYNPUF: Beneficiary Code'
             BENE_BIRTH_DT   length=4 format=YYMMDDN8. informat=yymmdd8.  label='DESYNPUF: Date of birth'
             BENE_DEATH_DT   length=4 format=YYMMDDN8. informat=yymmdd8.  label='DESYNPUF: Date of death'
             BENE_SEX_IDENT_CD  length=$1 format=$1.      label='DESYNPUF: Sex'
             BENE_RACE_CD    length=$1 format=$1.         label='DESYNPUF: Beneficiary Race Code'
             BENE_ESRD_IND   length=$1 format=$1.         label='DESYNPUF: End stage renal disease Indicator'
             SP_STATE_CODE      length=$2 format=$2.         label='DESYNPUF: State Code'
             BENE_COUNTY_CD  length=$3 format=$3.         label='DESYNPUF: County Code'
             BENE_HI_CVRAGE_TOT_MONS  length=3 format=2.  label='DESYNPUF: Total number of months of part A coverage for the beneficiary.'
             BENE_SMI_CVRAGE_TOT_MONS length=3 format=2.  label='DESYNPUF: Total number of months of part B coverage for the beneficiary.'
             BENE_HMO_CVRAGE_TOT_MONS length=3 format=2.  label='DESYNPUF: Total number of months of HMO coverage for the beneficiary.'
             PLAN_CVRG_MOS_NUM  length=$2 format=$2.      label='DESYNPUF: Total number of months of part D plan coverage for the beneficiary.'
             SP_ALZHDMTA     length=3 format=1.           label='DESYNPUF: Chronic Condition: Alzheimer or related disorders or senile'
             SP_CHF          length=3 format=1.           label='DESYNPUF: Chronic Condition: Heart Failure'
             SP_CHRNKIDN     length=3 format=1.           label='DESYNPUF: Chronic Condition: Chronic Kidney Disease'
             SP_CNCR         length=3 format=1.           label='DESYNPUF: Chronic Condition: Cancer'
             SP_COPD         length=3 format=1.           label='DESYNPUF: Chronic Condition: Chronic Obstructive Pulmonary Disease'
             SP_DEPRESSN     length=3 format=1.           label='DESYNPUF: Chronic Condition: Depression'
             SP_DIABETES     length=3 format=1.           label='DESYNPUF: Chronic Condition: Diabetes'
             SP_ISCHMCHT     length=3 format=1.           label='DESYNPUF: Chronic Condition: Ischemic Heart Disease'
             SP_OSTEOPRS     length=3 format=1.           label='DESYNPUF: Chronic Condition: Osteoporosis'
             SP_RA_OA        length=3 format=1.           label='DESYNPUF: Chronic Condition: RA/OA'
             SP_STRKETIA     length=3 format=1.           label='DESYNPUF: Chronic Condition: Stroke/transient Ischemic Attack'
             MEDREIMB_IP     length=8 format=10.2         label='DESYNPUF: Inpatient annual Medicare reimbursement amount'
             BENRES_IP       length=8 format=10.2         label='DESYNPUF: Inpatient annual beneficiary responsibility amount'
             PPPYMT_IP       length=8 format=10.2         label='DESYNPUF: Inpatient annual primary payer reimbursement amount'
             MEDREIMB_OP     length=8 format=10.2         label='DESYNPUF: Outpatient Institutional annual Medicare reimbursement amount'
             BENRES_OP       length=8 format=10.2         label='DESYNPUF: Outpatient Institutional annual beneficiary responsibility amount'
             PPPYMT_OP       length=8 format=10.2         label='DESYNPUF: Outpatient Institutional annual primary payer reimbursement amount'
             MEDREIMB_CAR    length=8 format=10.2         label='DESYNPUF: Carrier annual Medicare reimbursement amount'
             BENRES_CAR      length=8 format=10.2         label='DESYNPUF: Carrier annual beneficiary responsibility amount'
             PPPYMT_CAR      length=8 format=10.2         label='DESYNPUF: Carrier annual primary payer reimbursement amount'
          ;

      input DESYNPUF_ID
            BENE_BIRTH_DT
            BENE_DEATH_DT
            BENE_SEX_IDENT_CD
            BENE_RACE_CD
            BENE_ESRD_IND
            SP_STATE_CODE
            BENE_COUNTY_CD
            BENE_HI_CVRAGE_TOT_MONS
            BENE_SMI_CVRAGE_TOT_MONS
            BENE_HMO_CVRAGE_TOT_MONS
            PLAN_CVRG_MOS_NUM
            SP_ALZHDMTA
            SP_CHF
            SP_CHRNKIDN
            SP_CNCR
            SP_COPD
            SP_DEPRESSN
            SP_DIABETES
            SP_ISCHMCHT
            SP_OSTEOPRS
            SP_RA_OA
            SP_STRKETIA
            MEDREIMB_IP
            BENRES_IP
            PPPYMT_IP
            MEDREIMB_OP
            BENRES_OP
            PPPYMT_OP
            MEDREIMB_CAR
            BENRES_CAR
            PPPYMT_CAR;

    run;
    filename inbene clear;


    /*********************************************************************/
    /* Sort the data set if SORTDS=Y or SORTDS=YES.                      */
    /*********************************************************************/
    %if &sortds=Y or &sortds=YES %then %do;
      proc sort data=desynpuf.&outdsname&filenumber;
        by desynpuf_id;
      run;
    %end;

    /*********************************************************************/
    /* Examine new data set                                              */
    /*********************************************************************/
    title "Processing &infilename._&filenumber";
    proc contents data=desynpuf.&outdsname&filenumber varnum;
    run;
    proc print data=desynpuf.&outdsname&filenumber(obs=5);
      title2 'Subsample Listing - First 5 Rows';
    run;
    proc means data=desynpuf.&outdsname&filenumber;
      title2 'Simple Means';
    run;
    proc freq data=desynpuf.&outdsname&filenumber;
      title2 'Simple Frequencies';
      table bene_birth_dt bene_death_dt / missing;
      format bene_birth_dt bene_death_dt year4.;
    run;

  %end;

%mend desynpuf_bene_readin;

%macro desynpuf_bene_combine(startnumber=,endnumber=);
  %******************************************************************************;
  %* Macro program DESYNPUF_BENE_COMBINE concatenates several BENE data sets.    ;
  %* The data sets with the suffix starting with the numeric value assigned to   ;
  %* STARTNUMBER and ending with the numeric value assigned to ENDNUMBER are     ;
  %* concatenated.                                                               ;
  %*                                                                             ;
  %* Both the STARTNUMBER= and ENDNUMBER= parameters are required.               ;
  %*                                                                             ;
  %* After the new data set is created, output is generated                      ;
  %******************************************************************************;
  %local startyear endyear y i outdsname infilename;

  %let startyear=2008;
  %let endyear=2010;

  %do y=&startyear %to &endyear;
    %let outdsname=&&outdsname&y;
    %let infilename=&&infilename&y;

    data desynpuf.&outdsname(label="&infilename.&startnumber to &endnumber");
      set
      %do i=&startnumber %to &endnumber;
        desynpuf.&outdsname.&i
      %end;
      ;;;
      by desynpuf_id;
    run;

    /*********************************************************************/
    /* Examine new data set                                              */
    /*********************************************************************/
    title "Processing &infilename.&startnumber to &endnumber";
    proc contents data=desynpuf.&outdsname varnum;
    run;
    proc means data=desynpuf.&outdsname;
      title2 'Simple Means';
    run;
    proc freq data=desynpuf.&outdsname;
      title2 'Simple Frequencies';
      table bene_birth_dt bene_death_dt / missing;
      format bene_birth_dt bene_death_dt year4.;
    run;

  %end;

%mend desynpuf_bene_combine;

/*********************************************************************************/
/* END OF SECTION THAT SHOULD NOT BE MODIFIED.                                   */
/*********************************************************************************/
/*********************************************************************************/

/*********************************************************************************/
/* START OF SECTION THAT SHOULD BE REVIEWED AND/OR MODIFIED                      */
/*********************************************************************************/

/*********************************************************************************/
/* 5. Call macro program DESYNPUF_BENE_READIN once for BENE CSV file group of 3  */
/*    annual files (2008, 2009, 2010) you want to read in. Assign to FILENUMBER= */
/*    the numeric suffix (subsample number) of the CSV files for the group of    */
/*    annual files. Do not terminate the macro calls with a semicolon.           */
/*********************************************************************************/
%desynpuf_bene_readin(filenumber=1,sortds=no)
%desynpuf_bene_readin(filenumber=2,sortds=no)
%desynpuf_bene_readin(filenumber=3,sortds=no)
%desynpuf_bene_readin(filenumber=4,sortds=no)
%desynpuf_bene_readin(filenumber=5,sortds=no)
%desynpuf_bene_readin(filenumber=6,sortds=no)
%desynpuf_bene_readin(filenumber=7,sortds=no)
%desynpuf_bene_readin(filenumber=8,sortds=no)
%desynpuf_bene_readin(filenumber=9,sortds=no)
%desynpuf_bene_readin(filenumber=10,sortds=no)
%desynpuf_bene_readin(filenumber=11,sortds=no)
%desynpuf_bene_readin(filenumber=12,sortds=no)
%desynpuf_bene_readin(filenumber=13,sortds=no)
%desynpuf_bene_readin(filenumber=14,sortds=no)
%desynpuf_bene_readin(filenumber=15,sortds=no)
%desynpuf_bene_readin(filenumber=16,sortds=no)
%desynpuf_bene_readin(filenumber=17,sortds=no)
%desynpuf_bene_readin(filenumber=18,sortds=no)
%desynpuf_bene_readin(filenumber=19,sortds=no)
%desynpuf_bene_readin(filenumber=20,sortds=no)


/*********************************************************************************/
/* 6. OPTIONAL: Call macro program DESYNPUF_BENE_COMBINE if you want to          */
/*    concatenate the data sets created above that have consecutively numbered   */
/*    suffixes. Both STARTNUMBER= and ENDNUMBER= values must be specified.       */
/*    ENDNUMBER= must be greater than or equal to STARTNUMBER=. A data set will  */
/*    be created for each of the three years (2008, 2009, and 2010).             */
/*      If you want to combine data sets that are not consecutively numbered, you*/
/*    will need to write a DATA step to concatenate them.                        */
/*********************************************************************************/
%desynpuf_bene_combine(startnumber=1,endnumber=20)

/*********************************************************************************/
/* Clear some of the settings this program has made.                             */
/*********************************************************************************/
filename inbene clear;
libname desynpuf clear;

options validvarname=v7 nomprint ;

%symdel infilepath infilename2008 infilename2009 infilename2010
                   outdsname2008  outdsname2009  outdsname2010;
