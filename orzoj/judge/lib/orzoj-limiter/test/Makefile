SOURCES = $(wildcard *.cpp)
OBJS := $(patsubst %.cpp,%.o, $(SOURCES))
CXXFLAGS = -Wall -g -pthread
LDFLAGS = -pthread -lrt

all: main

%.d: %.cpp
	@set -e; rm -f $@; \
	$(CXX) -MM  $< >$@.$$$$; \
	sed 's,\($*\)\.o[ :]*,\1.o $@ : ,g' < $@.$$$$ > $@; \
	rm -f $@.$$$$

sinclude $(SOURCES:.cpp=.d)

main:$(OBJS)
	$(CXX) -o main $(OBJS) $(LDFLAGS)

clean:
	rm -f *.o test *.d

