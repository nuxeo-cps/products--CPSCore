.PHONY: clean

check:
	pychecker2 *.py

clean:
	find . -name '*~' | xargs rm -f
	find . -name '*pyc' | xargs rm -f
	rm -f ChangeLog
	cd tests ; make clean

