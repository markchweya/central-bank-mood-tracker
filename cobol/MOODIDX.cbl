      *================================================================*
      * MOODIDX - CENTRAL BANK MOOD INDEX BATCH JOB                    *
      *                                                                *
      * READS ONE RECORD PER SCORED SPEECH PARAGRAPH, SORTS THEM BY    *
      * COUNTRY AND MONTH, AND WRITES ONE INDEX RECORD PER COUNTRY-    *
      * MONTH PLUS A PRINTED SUMMARY REPORT PER COUNTRY.               *
      *                                                                *
      * STANCE INDEX  = (HAWKISH - DOVISH)    / LABELLED PARAGRAPHS    *
      * OUTLOOK INDEX = (POSITIVE - NEGATIVE) / LABELLED PARAGRAPHS    *
      * PARAGRAPHS LABELLED "none" DO NOT COUNT IN THE DENOMINATOR.    *
      * BOTH INDICES RUN FROM -1 TO +1.                                *
      *                                                                *
      * FILES (MAINFRAME-STYLE DD NAMES, SET AS ENVIRONMENT VARIABLES):*
      *   DD_SCORESIN   INPUT   CC YYYY-MM STANCE__ OUTLOOK_  (28 B)   *
      *   DD_INDEXOUT   OUTPUT  ONE LINE PER COUNTRY-MONTH    (44 B)   *
      *   DD_REPORTOUT  OUTPUT  132-COLUMN SUMMARY REPORT              *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MOODIDX.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SCORES-IN  ASSIGN TO SCORESIN
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-IN-STATUS.
           SELECT SORT-WORK  ASSIGN TO SORTWK.
           SELECT INDEX-OUT  ASSIGN TO INDEXOUT
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-OUT-STATUS.
           SELECT REPORT-OUT ASSIGN TO REPORTOUT
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-RPT-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  SCORES-IN.
       01  SCORE-REC.
           05  IN-COUNTRY              PIC X(2).
           05  FILLER                  PIC X.
           05  IN-MONTH                PIC X(7).
           05  FILLER                  PIC X.
           05  IN-STANCE               PIC X(8).
           05  FILLER                  PIC X.
           05  IN-OUTLOOK              PIC X(8).

       SD  SORT-WORK.
       01  SORT-REC.
           05  SR-COUNTRY              PIC X(2).
           05  SR-MONTH                PIC X(7).
           05  SR-STANCE               PIC X(8).
           05  SR-OUTLOOK              PIC X(8).

       FD  INDEX-OUT.
       01  INDEX-REC                   PIC X(44).

       FD  REPORT-OUT.
       01  REPORT-REC                  PIC X(132).

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS.
           05  WS-IN-STATUS            PIC XX.
           05  WS-OUT-STATUS           PIC XX.
           05  WS-RPT-STATUS           PIC XX.

       01  WS-FLAGS.
           05  WS-IN-EOF-SW            PIC X       VALUE "N".
               88  WS-IN-EOF                       VALUE "Y".
           05  WS-SORT-EOF-SW          PIC X       VALUE "N".
               88  WS-SORT-EOF                     VALUE "Y".

       01  WS-RUN-COUNTS.
           05  WS-READ                 PIC 9(7)    VALUE ZERO.
           05  WS-REJECTED             PIC 9(7)    VALUE ZERO.
           05  WS-RELEASED             PIC 9(7)    VALUE ZERO.
           05  WS-MONTHS-WRITTEN       PIC 9(7)    VALUE ZERO.
           05  WS-COUNTRIES            PIC 9(5)    VALUE ZERO.

       01  WS-CURRENT-KEY.
           05  WS-CUR-COUNTRY          PIC X(2).
           05  WS-CUR-MONTH            PIC X(7).

      *    TALLIES FOR THE COUNTRY-MONTH BEING BUILT.
       01  WS-MONTH-COUNTS.
           05  WM-PARAS                PIC 9(5).
           05  WM-HAWK                 PIC 9(5).
           05  WM-DOVE                 PIC 9(5).
           05  WM-STANCE-NEUTRAL       PIC 9(5).
           05  WM-POSITIVE             PIC 9(5).
           05  WM-NEGATIVE             PIC 9(5).
           05  WM-OUTLOOK-NEUTRAL      PIC 9(5).
           05  WM-N-STANCE             PIC 9(5).
           05  WM-N-OUTLOOK            PIC 9(5).
           05  WM-STANCE-IDX           PIC S9V9(4).
           05  WM-OUTLOOK-IDX          PIC S9V9(4).

      *    TOTALS FOR THE COUNTRY BEING BUILT.
       01  WS-COUNTRY-TOTALS.
           05  WC-MONTHS               PIC 9(5).
           05  WC-PARAS                PIC 9(7).
           05  WC-STANCE-MONTHS        PIC 9(5).
           05  WC-STANCE-SUM           PIC S9(5)V9(4).
           05  WC-OUTLOOK-MONTHS       PIC 9(5).
           05  WC-OUTLOOK-SUM          PIC S9(5)V9(4).
           05  WC-FIRST-MONTH          PIC X(7).
           05  WC-LAST-MONTH           PIC X(7).
           05  WC-AVG-STANCE           PIC S9V9(4).
           05  WC-AVG-OUTLOOK          PIC S9V9(4).

       01  WS-INDEX-LINE.
           05  WL-COUNTRY              PIC X(2).
           05  FILLER                  PIC X       VALUE SPACE.
           05  WL-MONTH                PIC X(7).
           05  FILLER                  PIC X       VALUE SPACE.
           05  WL-N-PARAS              PIC 9(5).
           05  FILLER                  PIC X       VALUE SPACE.
           05  WL-N-STANCE             PIC 9(5).
           05  FILLER                  PIC X       VALUE SPACE.
           05  WL-STANCE-IDX           PIC -9.9999.
           05  FILLER                  PIC X       VALUE SPACE.
           05  WL-N-OUTLOOK            PIC 9(5).
           05  FILLER                  PIC X       VALUE SPACE.
           05  WL-OUTLOOK-IDX          PIC -9.9999.

       01  WS-RUN-DATE.
           05  WS-RUN-YYYY             PIC X(4).
           05  WS-RUN-MM               PIC X(2).
           05  WS-RUN-DD               PIC X(2).
           05  FILLER                  PIC X(13).

       01  RPT-TITLE.
           05  FILLER                  PIC X(40)
               VALUE "CENTRAL BANK MOOD TRACKER - MOOD INDEX".
           05  FILLER                  PIC X(10)   VALUE "RUN DATE ".
           05  RT-YYYY                 PIC X(4).
           05  FILLER                  PIC X       VALUE "-".
           05  RT-MM                   PIC X(2).
           05  FILLER                  PIC X       VALUE "-".
           05  RT-DD                   PIC X(2).

       01  RPT-HEADING.
           05  FILLER                  PIC X(9)    VALUE "COUNTRY".
           05  FILLER                  PIC X(10)   VALUE "FIRST".
           05  FILLER                  PIC X(10)   VALUE "LAST".
           05  FILLER                  PIC X(9)    VALUE "MONTHS".
           05  FILLER                  PIC X(12)   VALUE "PARAGRAPHS".
           05  FILLER                  PIC X(13)   VALUE "AVG STANCE".
           05  FILLER                  PIC X(13)   VALUE "AVG OUTLOOK".

       01  RPT-RULE                    PIC X(76)   VALUE ALL "-".

       01  RPT-DETAIL.
           05  RD-COUNTRY              PIC X(2).
           05  FILLER                  PIC X(7)    VALUE SPACES.
           05  RD-FIRST                PIC X(7).
           05  FILLER                  PIC X(3)    VALUE SPACES.
           05  RD-LAST                 PIC X(7).
           05  FILLER                  PIC X(3)    VALUE SPACES.
           05  RD-MONTHS               PIC ZZ,ZZ9.
           05  FILLER                  PIC X(3)    VALUE SPACES.
           05  RD-PARAS                PIC Z,ZZZ,ZZ9.
           05  FILLER                  PIC X(6)    VALUE SPACES.
           05  RD-AVG-STANCE           PIC -9.9999.
           05  FILLER                  PIC X(6)    VALUE SPACES.
           05  RD-AVG-OUTLOOK          PIC -9.9999.

       01  RPT-TOTALS.
           05  FILLER                  PIC X(20)
               VALUE "RECORDS READ".
           05  RX-READ                 PIC Z,ZZZ,ZZ9.
           05  FILLER                  PIC X(14)   VALUE "   REJECTED".
           05  RX-REJECTED             PIC Z,ZZZ,ZZ9.
           05  FILLER                  PIC X(16)
               VALUE "   INDEX LINES".
           05  RX-MONTHS               PIC Z,ZZZ,ZZ9.

       PROCEDURE DIVISION.
       000-MAIN.
           PERFORM 050-OPEN-OUTPUTS
           SORT SORT-WORK
               ON ASCENDING KEY SR-COUNTRY SR-MONTH
               INPUT PROCEDURE  IS 100-LOAD-SCORES
               OUTPUT PROCEDURE IS 200-BUILD-INDEX
           PERFORM 900-FINISH
           STOP RUN.

       050-OPEN-OUTPUTS.
           OPEN OUTPUT INDEX-OUT
           IF WS-OUT-STATUS NOT = "00"
               DISPLAY "MOODIDX: CANNOT OPEN INDEXOUT, STATUS "
                   WS-OUT-STATUS
               MOVE 8 TO RETURN-CODE
               STOP RUN
           END-IF
           OPEN OUTPUT REPORT-OUT
           IF WS-RPT-STATUS NOT = "00"
               DISPLAY "MOODIDX: CANNOT OPEN REPORTOUT, STATUS "
                   WS-RPT-STATUS
               MOVE 8 TO RETURN-CODE
               STOP RUN
           END-IF
           MOVE FUNCTION CURRENT-DATE TO WS-RUN-DATE
           MOVE WS-RUN-YYYY TO RT-YYYY
           MOVE WS-RUN-MM   TO RT-MM
           MOVE WS-RUN-DD   TO RT-DD
           WRITE REPORT-REC FROM RPT-TITLE
           MOVE SPACES TO REPORT-REC
           WRITE REPORT-REC
           WRITE REPORT-REC FROM RPT-HEADING
           WRITE REPORT-REC FROM RPT-RULE.

      *----------------------------------------------------------------*
      * INPUT PROCEDURE: VALIDATE EACH SCORE RECORD AND RELEASE IT.    *
      *----------------------------------------------------------------*
       100-LOAD-SCORES.
           OPEN INPUT SCORES-IN
           IF WS-IN-STATUS NOT = "00"
               DISPLAY "MOODIDX: CANNOT OPEN SCORESIN, STATUS "
                   WS-IN-STATUS
               MOVE 8 TO RETURN-CODE
               STOP RUN
           END-IF
           PERFORM 110-READ-SCORE
           PERFORM UNTIL WS-IN-EOF
               PERFORM 120-CHECK-AND-RELEASE
               PERFORM 110-READ-SCORE
           END-PERFORM
           CLOSE SCORES-IN.

       110-READ-SCORE.
           READ SCORES-IN
               AT END SET WS-IN-EOF TO TRUE
               NOT AT END ADD 1 TO WS-READ
           END-READ.

       120-CHECK-AND-RELEASE.
           IF IN-COUNTRY = SPACES OR IN-MONTH(5:1) NOT = "-"
               ADD 1 TO WS-REJECTED
           ELSE
               EVALUATE TRUE
                   WHEN IN-STANCE NOT = "hawkish" AND NOT = "dovish"
                        AND NOT = "neutral" AND NOT = "none"
                       ADD 1 TO WS-REJECTED
                   WHEN IN-OUTLOOK NOT = "positive" AND NOT = "negative"
                        AND NOT = "neutral" AND NOT = "none"
                       ADD 1 TO WS-REJECTED
                   WHEN OTHER
                       MOVE IN-COUNTRY TO SR-COUNTRY
                       MOVE IN-MONTH   TO SR-MONTH
                       MOVE IN-STANCE  TO SR-STANCE
                       MOVE IN-OUTLOOK TO SR-OUTLOOK
                       RELEASE SORT-REC
                       ADD 1 TO WS-RELEASED
               END-EVALUATE
           END-IF.

      *----------------------------------------------------------------*
      * OUTPUT PROCEDURE: CONTROL BREAK ON COUNTRY, THEN ON MONTH.     *
      *----------------------------------------------------------------*
       200-BUILD-INDEX.
           PERFORM 210-RETURN-NEXT
           PERFORM UNTIL WS-SORT-EOF
               MOVE SR-COUNTRY TO WS-CUR-COUNTRY
               PERFORM 300-START-COUNTRY
               PERFORM UNTIL WS-SORT-EOF
                       OR SR-COUNTRY NOT = WS-CUR-COUNTRY
                   MOVE SR-MONTH TO WS-CUR-MONTH
                   INITIALIZE WS-MONTH-COUNTS
                   PERFORM UNTIL WS-SORT-EOF
                           OR SR-COUNTRY NOT = WS-CUR-COUNTRY
                           OR SR-MONTH NOT = WS-CUR-MONTH
                       PERFORM 220-TALLY
                       PERFORM 210-RETURN-NEXT
                   END-PERFORM
                   PERFORM 230-WRITE-MONTH
               END-PERFORM
               PERFORM 310-END-COUNTRY
           END-PERFORM.

       210-RETURN-NEXT.
           RETURN SORT-WORK
               AT END SET WS-SORT-EOF TO TRUE
           END-RETURN.

       220-TALLY.
           ADD 1 TO WM-PARAS
           EVALUATE SR-STANCE
               WHEN "hawkish"  ADD 1 TO WM-HAWK
               WHEN "dovish"   ADD 1 TO WM-DOVE
               WHEN "neutral"  ADD 1 TO WM-STANCE-NEUTRAL
               WHEN OTHER      CONTINUE
           END-EVALUATE
           EVALUATE SR-OUTLOOK
               WHEN "positive" ADD 1 TO WM-POSITIVE
               WHEN "negative" ADD 1 TO WM-NEGATIVE
               WHEN "neutral"  ADD 1 TO WM-OUTLOOK-NEUTRAL
               WHEN OTHER      CONTINUE
           END-EVALUATE.

       230-WRITE-MONTH.
           COMPUTE WM-N-STANCE = WM-HAWK + WM-DOVE + WM-STANCE-NEUTRAL
           COMPUTE WM-N-OUTLOOK =
               WM-POSITIVE + WM-NEGATIVE + WM-OUTLOOK-NEUTRAL
           MOVE ZERO TO WM-STANCE-IDX WM-OUTLOOK-IDX
           IF WM-N-STANCE > ZERO
               COMPUTE WM-STANCE-IDX ROUNDED =
                   (WM-HAWK - WM-DOVE) / WM-N-STANCE
               ADD 1 TO WC-STANCE-MONTHS
               ADD WM-STANCE-IDX TO WC-STANCE-SUM
           END-IF
           IF WM-N-OUTLOOK > ZERO
               COMPUTE WM-OUTLOOK-IDX ROUNDED =
                   (WM-POSITIVE - WM-NEGATIVE) / WM-N-OUTLOOK
               ADD 1 TO WC-OUTLOOK-MONTHS
               ADD WM-OUTLOOK-IDX TO WC-OUTLOOK-SUM
           END-IF

           MOVE WS-CUR-COUNTRY TO WL-COUNTRY
           MOVE WS-CUR-MONTH   TO WL-MONTH
           MOVE WM-PARAS       TO WL-N-PARAS
           MOVE WM-N-STANCE    TO WL-N-STANCE
           MOVE WM-STANCE-IDX  TO WL-STANCE-IDX
           MOVE WM-N-OUTLOOK   TO WL-N-OUTLOOK
           MOVE WM-OUTLOOK-IDX TO WL-OUTLOOK-IDX
           WRITE INDEX-REC FROM WS-INDEX-LINE
           ADD 1 TO WS-MONTHS-WRITTEN

           ADD 1 TO WC-MONTHS
           ADD WM-PARAS TO WC-PARAS
           IF WC-FIRST-MONTH = SPACES
               MOVE WS-CUR-MONTH TO WC-FIRST-MONTH
           END-IF
           MOVE WS-CUR-MONTH TO WC-LAST-MONTH.

       300-START-COUNTRY.
           INITIALIZE WS-COUNTRY-TOTALS
           MOVE SPACES TO WC-FIRST-MONTH WC-LAST-MONTH.

       310-END-COUNTRY.
           MOVE ZERO TO WC-AVG-STANCE WC-AVG-OUTLOOK
           IF WC-STANCE-MONTHS > ZERO
               COMPUTE WC-AVG-STANCE ROUNDED =
                   WC-STANCE-SUM / WC-STANCE-MONTHS
           END-IF
           IF WC-OUTLOOK-MONTHS > ZERO
               COMPUTE WC-AVG-OUTLOOK ROUNDED =
                   WC-OUTLOOK-SUM / WC-OUTLOOK-MONTHS
           END-IF
           MOVE WS-CUR-COUNTRY TO RD-COUNTRY
           MOVE WC-FIRST-MONTH TO RD-FIRST
           MOVE WC-LAST-MONTH  TO RD-LAST
           MOVE WC-MONTHS      TO RD-MONTHS
           MOVE WC-PARAS       TO RD-PARAS
           MOVE WC-AVG-STANCE  TO RD-AVG-STANCE
           MOVE WC-AVG-OUTLOOK TO RD-AVG-OUTLOOK
           WRITE REPORT-REC FROM RPT-DETAIL
           ADD 1 TO WS-COUNTRIES.

       900-FINISH.
           WRITE REPORT-REC FROM RPT-RULE
           MOVE WS-READ           TO RX-READ
           MOVE WS-REJECTED       TO RX-REJECTED
           MOVE WS-MONTHS-WRITTEN TO RX-MONTHS
           WRITE REPORT-REC FROM RPT-TOTALS
           CLOSE INDEX-OUT REPORT-OUT
           DISPLAY "MOODIDX: READ " WS-READ
               " REJECTED " WS-REJECTED
               " COUNTRIES " WS-COUNTRIES
               " INDEX LINES " WS-MONTHS-WRITTEN
           IF WS-REJECTED > ZERO
               MOVE 4 TO RETURN-CODE
           END-IF.
