.PHONY: clean check

check:
	pychecker2 *.py

clean:
	find . "(" -name "*~" -or -name "*.pyc" ")" -print0 | xargs -0 rm -f
	rm -f ChangeLog
	cd tests ; make clean

