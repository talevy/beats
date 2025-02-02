# -*- coding: utf-8 -*-

from filebeat import TestCase

import codecs
import os
import time


# Additional tests to be added:
# * Check what happens when file renamed -> no recrawling should happen
# * Check if file descriptor is "closed" when file disappears
class Test(TestCase):
    def test_fetched_lines(self):
        """
        Checks if all lines are read from the log file.
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w')

        iterations = 80
        for n in range(0, iterations):
            file.write("hello world" + str(n))
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        self.wait_until(
            lambda: self.log_contains(
                "Processing 80 events"),
            max_timeout=15)

        # TODO: Find better solution when filebeat did crawl the file
        # Idea: Special flag to filebeat so that filebeat is only doing and
        # crawl and then finishes
        filebeat.kill_and_wait()

        output = self.read_output()

        # Check that output file has the same number of lines as the log file
        assert iterations == len(output)

    def test_unfinished_line_and_continue(self):
        """
        Checks that if a line does not have a line ending, is is not read yet.
        Continuing writing the file must the pick up the line.
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w', 0)

        iterations = 80
        for n in range(0, iterations):
            file.write("hello world" + str(n))
            file.write("\n")

        # An additional line is written to the log file. This line should not
        # be read as there is no finishing \n or \r
        file.write("unfinished line")

        filebeat = self.start_filebeat()

        self.wait_until(
            lambda: self.output_has(lines=80),
            max_timeout=15)

        # Give it more time to make sure it doesn't read the unfinished line
        # This mus be smaller then partial_line_waiting
        time.sleep(1)

        output = self.read_output()

        # Check that output file has the same number of lines as the log file
        assert iterations == len(output)

        # Complete line so it can be picked up
        file.write("\n")
        self.wait_until(
            lambda: self.output_has(lines=81),
            max_timeout=15)

        # Add one more line to make sure it keeps reading
        file.write("HelloWorld \n")
        file.close()

        self.wait_until(
            lambda: self.output_has(lines=82),
            max_timeout=15)

        filebeat.kill_and_wait()

        output = self.read_output()

        # Check that output file has also the completed lines
        assert iterations + 2 == len(output)

    def test_partial_line(self):
        """
        Checks that partial lines are read as intended
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*",
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w', 0)

        # An additional line is written to the log file. This line should not
        # be read as there is no finishing \n or \r
        file.write("complete line\n")
        file.write("unfinished line ")

        filebeat = self.start_filebeat()

        # Check that unfinished line is read after timeout and sent
        self.wait_until(
            lambda: self.output_has(lines=1),
            max_timeout=15)

        file.write("extend unfinished line")
        time.sleep(1)

        # Check that unfinished line is still not read
        self.wait_until(
            lambda: self.output_has(lines=1),
            max_timeout=15)

        file.write("\n")

        # Check that unfinished line is now read
        self.wait_until(
            lambda: self.output_has(lines=2),
            max_timeout=15)

        file.write("hello world\n")

        # Check that new line is read
        self.wait_until(
            lambda: self.output_has(lines=3),
            max_timeout=15)

        filebeat.kill_and_wait()

    def test_file_renaming(self):
        """
        Makes sure that when a file is renamed, the content is not read again.
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile1 = self.working_dir + "/log/test-old.log"
        file = open(testfile1, 'w')

        iterations = 5
        for n in range(0, iterations):
            file.write("old file")
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        self.wait_until(
            lambda: self.log_contains(
                "Processing 5 events"),
            max_timeout=15)

        # Rename the file (no new file created)
        testfile2 = self.working_dir + "/log/test-new.log"
        os.rename(testfile1, testfile2)
        file = open(testfile2, 'a')

        # using 6 events to have a separate log line that we can
        # grep for.
        iterations = 6
        for n in range(0, iterations):
            file.write("new file")
            file.write("\n")

        file.close()

        # expecting 6 more events
        self.wait_until(
            lambda: self.log_contains(
                "Processing 6 events"),
            max_timeout=20)

        filebeat.kill_and_wait()

        output = self.read_output()

        # Make sure all 11 lines were read
        assert len(output) == 11

    def test_file_disappear(self):
        """
        Checks that filebeat keeps running in case a log files is deleted
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w')

        iterations = 5
        for n in range(0, iterations):
            file.write("disappearing file")
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        # Let it read the file
        self.wait_until(
            lambda: self.log_contains(
                "Processing 5 events"),
            max_timeout=15)
        os.remove(testfile)

        # Create new file to check if new file is picked up
        testfile2 = self.working_dir + "/log/test2.log"
        file = open(testfile2, 'w')

        iterations = 6
        for n in range(0, iterations):
            file.write("new file")
            file.write("\n")

        file.close()

        # Let it read the file
        self.wait_until(
            lambda: self.log_contains(
                "Processing 6 events"),
            max_timeout=15)

        filebeat.kill_and_wait()

        data = self.get_dot_filebeat()

        # Make sure new file was picked up, old file should stay in
        assert len(data) == 2

        # Make sure output has 10 entries
        output = self.read_output()

        assert len(output) == 5 + 6

    def test_file_disappear_appear(self):
        """
        Checks that filebeat keeps running in case a log files is deleted

        On Windows this tests in addition if the file was closed as it couldn't be found anymore
        If Windows does not close the file, a new one can't be created.
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*",
            force_close_files="true",
            scan_frequency="0.1s"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w')

        iterations1 = 5
        for n in range(0, iterations1):
            file.write("disappearing file")
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        # Let it read the file
        self.wait_until(
            lambda: self.output_has(lines=iterations1), max_timeout=10)
        os.remove(testfile)

        # Wait until error shows up on windows
        self.wait_until(
            lambda: self.log_contains(
                "Force close file"),
            max_timeout=15)

        # Create new file with same name to see if it is picked up
        file = open(testfile, 'w')

        iterations2 = 6
        for n in range(0, iterations2):
            file.write("new file")
            file.write("\n")

        file.close()

        # Let it read the file
        self.wait_until(
            lambda: self.output_has(lines=iterations1+iterations2), max_timeout=10)

        filebeat.kill_and_wait()

        data = self.get_dot_filebeat()

        # Make sure new file was picked up. As it has the same file name,
        # only one entry exists
        assert len(data) == 1

        # Make sure output has 11 entries, the new file was started
        # from scratch
        output = self.read_output()
        assert len(output) == 5 + 6

    def test_force_close(self):
        """
        Checks that a file is closed in case it is rotated
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/test.log",
            force_close_files="true",
            scan_frequency="0.1s"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile1 = self.working_dir + "/log/test.log"
        testfile2 = self.working_dir + "/log/test.log.rotated"
        file = open(testfile1, 'w')

        iterations1 = 5
        for n in range(0, iterations1):
            file.write("rotation file")
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        # Let it read the file
        self.wait_until(
            lambda: self.output_has(lines=iterations1), max_timeout=10)

        os.rename(testfile1, testfile2)

        file = open(testfile1, 'w', 0)
        file.write("Hello World\n")
        file.close()

        # Wait until error shows up on windows
        self.wait_until(
            lambda: self.log_contains(
                "Force close file"),
            max_timeout=15)

        # Let it read the file
        self.wait_until(
            lambda: self.output_has(lines=iterations1+1), max_timeout=10)

        filebeat.kill_and_wait()

        data = self.get_dot_filebeat()

        # Make sure new file was picked up. As it has the same file name,
        # only one entry exists
        assert len(data) == 1

        # Make sure output has 11 entries, the new file was started
        # from scratch
        output = self.read_output()
        #assert len(output) == 5 + 6


    def test_new_line_on_existing_file(self):
        """
        Checks that filebeat follows future writes to the same
        file.
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        with open(testfile, 'w') as f:
            f.write("hello world\n")

        filebeat = self.start_filebeat()

        self.wait_until(
            lambda: self.log_contains(
                "Processing 1 events"),
            max_timeout=15)

        with open(testfile, 'a') as f:
            # now write another line
            f.write("hello world 1\n")
            f.write("hello world 2\n")

        self.wait_until(
            lambda: self.log_contains(
                "Processing 2 events"),
            max_timeout=15)

        filebeat.kill_and_wait()

        # Check that output file has the same number of lines as the log file
        output = self.read_output()
        assert len(output) == 3

    def test_multiple_appends(self):
        """
        Test that filebeat keeps picking up new lines
        after appending multiple times
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"

        filebeat = self.start_filebeat()

        # Write initial file
        with open(testfile, 'w') as f:
            f.write("hello world\n")
            f.flush()

            self.wait_until(
                lambda: self.output_has(1),
                max_timeout=15)

        lines_written = 0

        for n in range(3):
            with open(testfile, 'a') as f:

                for i in range(0, 20 + n):
                    f.write("hello world " + str(i) + " " + str(n) + "\n")
                    lines_written = lines_written + 1

                f.flush()

                self.wait_until(
                    lambda: self.output_has( lines_written + 1),
                    max_timeout=15)

        filebeat.kill_and_wait()

        # Check that output file has the same number of lines as the log file
        output = self.read_output()
        assert len(output) == (3 * 20 + sum(range(0, 3)) + 1)

    def test_new_line_on_open_file(self):
        """
        Checks that filebeat follows future writes to the same
        file. Same as the test_new_line_on_existing_file but this
        time keep the file open and just flush it.
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        with open(testfile, 'w') as f:
            f.write("hello world\n")
            f.flush()

            filebeat = self.start_filebeat()

            self.wait_until(
                lambda: self.log_contains(
                    "Processing 1 events"),
                max_timeout=15)

            # now write another line
            f.write("hello world 1\n")
            f.write("hello world 2\n")
            f.flush()

            self.wait_until(
                lambda: self.log_contains(
                    "Processing 2 events"),
                max_timeout=15)

        filebeat.kill_and_wait()

        # Check that output file has the same number of lines as the log file
        output = self.read_output()
        assert len(output) == 3

    def test_tail_files(self):
        """
        Tests that every new file discovered is started
        at the end and not beginning
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*",
            tailFiles="true"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        with open(testfile, 'w') as f:
            # Write lines before registar started
            f.write("hello world 1\n")
            f.write("hello world 2\n")
            f.flush()

        filebeat = self.start_filebeat()
        self.wait_until(
            lambda: self.log_contains(
                "Start next scan"),
            max_timeout=5)

        with open(testfile, 'a') as f:
            # write additional lines
            f.write("hello world 3\n")
            f.write("hello world 4\n")
            f.flush()


        self.wait_until(
            lambda: self.output_has(lines=2),
            max_timeout=15)

        filebeat.kill_and_wait()

        # Make sure output has only 2 and not 4 lines, means it started at
        # the end
        output = self.read_output()
        assert len(output) == 2

    def test_utf8(self):
        """
        Tests that UTF-8 chars don't break our log tailing.
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*",
            encoding="utf-8"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"

        filebeat = self.start_filebeat()
        self.wait_until(
            lambda: self.log_contains(
                "Start next scan"),
            max_timeout=15)

        # Add utf-8 Chars for the first time
        with codecs.open(testfile, "w", "utf-8") as f:
            # Write lines before registar started

            # Special encoding needed?!?
            f.write("ニコラスRuflin".decode("utf-8") + "\n")
            f.flush()

            self.wait_until(
                lambda: self.log_contains(
                    "Processing 1 events"),
                max_timeout=15)

        # Append utf-8 chars to check if it keeps reading
        with codecs.open(testfile, "a") as f:
            # write additional lines
            f.write("Hello\n")
            f.write("薩科Ruflin" + "\n")
            f.flush()

            self.wait_until(
                lambda: self.log_contains(
                    "Processing 2 events"),
                max_timeout=15)

        filebeat.kill_and_wait()

        # Make sure output has 3
        output = self.read_output()
        assert len(output) == 3

    def test_encodings(self):
        """
        Tests that several common encodings work.
        """

        # Sample texts are from http://www.columbia.edu/~kermit/utf8.html
        encodings = [
            # golang, python, sample text
            ("plain", "ascii", u"I can eat glass"),
            ("utf-8", "utf_8",
             u"ὕαλον ϕαγεῖν δύναμαι· τοῦτο οὔ με βλάπτει."),
            ("utf-16be", "utf_16_be",
             u"Pot să mănânc sticlă și ea nu mă rănește."),
            ("utf-16le", "utf_16_le",
             u"काचं शक्नोम्यत्तुम् । नोपहिनस्ति माम् ॥"),
            ("latin1", "latin1",
             u"I kå Glas frässa, ond des macht mr nix!"),
            ("BIG5", "big5", u"我能吞下玻璃而不傷身體。"),
            ("gb18030", "gb18030", u"我能吞下玻璃而不傷身。體"),
            ("euc-kr", "euckr", u" 나는 유리를 먹을 수 있어요. 그래도 아프지 않아요"),
            ("euc-jp", "eucjp", u"私はガラスを食べられます。それは私を傷つけません。")
        ]

        # create a file in each encoding
        os.mkdir(self.working_dir + "/log/")
        for _, enc_py, text in encodings:
            with codecs.open(self.working_dir + "/log/test-{}".format(enc_py),
                             "w", enc_py) as f:
                f.write(text + "\n")

        # create the config file
        prospectors = []
        for enc_go, enc_py, _ in encodings:
            prospectors.append({
                "path": self.working_dir + "/log/test-{}".format(enc_py),
                "encoding": enc_go
            })
        self.render_config_template(
            template="filebeat_prospectors.yml.j2",
            prospectors=prospectors
        )

        # run filebeat
        filebeat = self.start_filebeat()
        self.wait_until(lambda: self.output_has(lines=len(encodings)),
                        max_timeout=15)

        # write another line in all files
        for _, enc_py, text in encodings:
            with codecs.open(self.working_dir + "/log/test-{}".format(enc_py),
                             "a", enc_py) as f:
                f.write(text + " 2" + "\n")

        # wait again
        self.wait_until(lambda: self.output_has(lines=len(encodings)*2),
                        max_timeout=15)
        filebeat.kill_and_wait()

        # check that all outputs are present in the JSONs in UTF-8
        # encoding
        output = self.read_output()
        lines = [o["message"] for o in output]
        for _, _, text in encodings:
            assert text in lines
            assert text + " 2" in lines

    def test_include_lines(self):
        """
        Checks if only the log lines defined by include_lines are exported
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*",
            include_lines=["^ERR", "^WARN"]
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w')

        iterations = 20
        for n in range(0, iterations):
            file.write("DBG: a simple debug message" + str(n))
            file.write("\n")
            file.write("ERR: a simple error message" + str(n))
            file.write("\n")
            file.write("WARNING: a simple warning message" + str(n))
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        self.wait_until(
            lambda: self.output_has(40),
            max_timeout=15)

        # TODO: Find better solution when filebeat did crawl the file
        # Idea: Special flag to filebeat so that filebeat is only doing and
        # crawl and then finishes
        filebeat.kill_and_wait()

        output = self.read_output()

        # Check that output file has the same number of lines as the log file
        assert iterations*2 == len(output)

    def test_default_include_exclude_lines(self):
        """
        Checks if all the log lines are exported by default
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*"
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w')

        iterations = 20
        for n in range(0, iterations):
            file.write("DBG: a simple debug message" + str(n))
            file.write("\n")
            file.write("ERR: a simple error message" + str(n))
            file.write("\n")
            file.write("WARNING: a simple warning message" + str(n))
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        self.wait_until(
            lambda: self.output_has(60),
            max_timeout=15)

        # TODO: Find better solution when filebeat did crawl the file
        # Idea: Special flag to filebeat so that filebeat is only doing and
        # crawl and then finishes
        filebeat.kill_and_wait()

        output = self.read_output()

        # Check that output file has the same number of lines as the log file
        assert iterations*3 == len(output)

    def test_exclude_lines(self):
        """
        Checks if the lines matching exclude_lines regexp are dropped
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*",
            exclude_lines=["^DBG"]
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w')

        iterations = 20
        for n in range(0, iterations):
            file.write("DBG: a simple debug message" + str(n))
            file.write("\n")
            file.write("ERR: a simple error message" + str(n))
            file.write("\n")
            file.write("WARNING: a simple warning message" + str(n))
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        self.wait_until(
            lambda: self.output_has(40),
            max_timeout=15)

        # TODO: Find better solution when filebeat did crawl the file
        # Idea: Special flag to filebeat so that filebeat is only doing and
        # crawl and then finishes
        filebeat.kill_and_wait()

        output = self.read_output()

        # Check that output file has the same number of lines as the log file
        assert iterations*2 == len(output)

    def test_include_exclude_lines(self):
        """
        Checks if all the log lines are exported by default
        """

        self.render_config_template(
            path=os.path.abspath(self.working_dir) + "/log/*",
            exclude_lines=["^DBG"],
            include_lines=["apache"]
        )
        os.mkdir(self.working_dir + "/log/")

        testfile = self.working_dir + "/log/test.log"
        file = open(testfile, 'w')

        iterations = 20
        for n in range(0, iterations):
            file.write("DBG: a simple debug message" + str(n))
            file.write("\n")
            file.write("ERR: apache simple error message" + str(n))
            file.write("\n")
            file.write("ERR: a simple warning message" + str(n))
            file.write("\n")

        file.close()

        filebeat = self.start_filebeat()

        self.wait_until(
            lambda: self.output_has(20),
            max_timeout=15)

        # TODO: Find better solution when filebeat did crawl the file
        # Idea: Special flag to filebeat so that filebeat is only doing and
        # crawl and then finishes
        filebeat.kill_and_wait()

        output = self.read_output()

        # Check that output file has the same number of lines as the log file
        assert iterations == len(output)
