STXHTML := $(shell ls *.stx | sed -e s/.stx/.html/)

all: ${STXHTML}

clean: 
	rm -f ${STXHTML}
  
%.html: %.stx
	@stx2html $<

# vim:noet
