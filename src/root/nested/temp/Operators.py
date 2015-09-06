"""This module has functions that convert operations on standard Python data structures
to operations on streams.

The module has three collections of functions:
(1) functions that convert operations on standard Python data structures
to operations on streams. These functions operate on a list of input
streams to generate a list of output streams. The functions deal with
the following data structures: lists, elements of lists, (moving)
windows, and timed windows.
(2) functions that map the general case of multiple input streams and
multiple output streams described above to the following special cases:
  (a) merge: an arbitrary number of input streams and a single output stream.
  (b) split: a single input stream and an arbitrary number of output streams.
  (c) op: a single input stream and a single output stream.
  (d) source: no input and an arbitrary number of output streams.
  (e) sink: no ouput and an arbitrary number of input streams.
  These special cases simplify that functions that need to be written
  for standard Python data structures. You can always use the arbitrary
  number of inputs and outputs case even if there is only one or zero input
  or output streams. The functions for merge, split, op, source, and sink
  are simpler than the general case; so use them, where appropriate.
(3) a function that provides a single common signature for converting
operations on Python structures to operations on streams regardless of
whether the function has no inputs, a single input stream, a list of
input streams, or no outputs, a single output stream or a list of output
streams.

"""
if __name__ == '__main__':
    if __package__ is None:
        import sys
        from os import path
        sys.path.append(path.dirname(
            path.dirname(path.abspath(__file__))))

from Agent import *
from Stream import *
from Stream import _no_value, _multivalue

# ASSERTIONS USED IN FILE
def assert_is_list_of_streams_or_None(x):
    assert isinstance(x, list) or isinstance(x, tuple) or x is None,\
      'Expected {0} to be None or list or tuple.'.format(x)
    if x is not None:
        assert all(isinstance(l, Stream) for l in x),\
          'Expected {0} to be a list (or tuple) of streams.'.format(x)

def assert_is_list_of_streams(x):
    assert isinstance(x, list) or isinstance(x, tuple),\
      'Expected {0} to be a list or tuple'.format(x)
    assert all(isinstance(l, Stream) for l in x),\
      'Expected {0} to be a list (or tuple) of streams'.format(x)

def assert_is_list_of_lists(x, list_size=None):
    assert isinstance(x, list) or isinstance(x, tuple),\
      'Expected {0} to be a list or tuple'.format(x)
    assert all((isinstance(l, list) or isinstance(l, np.ndarray)) for l in x),\
      'Expected {0} to be a list (or tuple) or np.ndarray of lists'.format(x)
    assert list_size is None or list_size == len(x), \
      'Expected len({0}) == {1}, or {1} to be None'.format(x, list_size)
    
def assert_is_list_or_None(x):
    assert isinstance(x, list) or x is None, \
      'Expected {0} to be a list or None'.format(x)

def assert_is_list(x):
    assert isinstance(x, list), \
      'Expected {0} to be a list'.format(x)

def remove_novalue_and_open_multivalue(l):
    """ This function returns a list which is the
    same as the input parameter l except that
    (1) _no_value elements in l are deleted and
    (2) each _multivalue element in l is opened
        i.e., for an object _multivalue(list_x)
        each element of list_x appears in the
        returned list.

    """
    return_list = []
    if not isinstance(l, list):
        return l
    for v in l:
        if v == _no_value:
            continue
        elif isinstance(v, _multivalue):
            return_list.extend(v.lst)
        else:
            return_list.append(v)
    return return_list


"""PART 1 OF MODULE
Functions that convert operations on non-streaming data structures
to operations on streams. The data structures and corresponding functions are:
  (a) lists: list_func
  (b) single elements of list: element_func
  (c) moving windows: window_func
  (d) timed windows: timed_func
Each of these functions has the following parameters:
f, inputs, num_outputs, state, call_streams
where:
  f is a Python function on non-streaming data structures.
   for list_func, f: list of lists, state -> list of lists, state
   for element_funct, f: list, state -> list, state
   for window_func, f: list, state -> element, state
   for timed_func, f: timed list, state -> timed element, state
     where a timed element has a time field and a value field.

"""

def list_func(f, inputs, num_outputs, state, call_streams,
              window_size, step_size):
    # f: list of lists, state -> list of lists, state
    assert_is_list_of_streams_or_None(call_streams)

    def transition(in_lists, state):
        smallest_list_length = min(v.stop - v.start for v in in_lists)
        input_lists = [v.list[v.start:v.start+smallest_list_length] for v in in_lists]
        if not input_lists:
            return ([[]]*num_outputs, state, [v.start for v in in_lists])
        if state is None:
            output_lists = f(input_lists)
        else:
            output_lists, state = f(input_lists, state)

        if num_outputs:
            assert_is_list_of_lists(output_lists, num_outputs)
        in_lists_start_values = [v.start+smallest_list_length for v in in_lists]
        return (output_lists, state, in_lists_start_values)

    # Create agent
    output_streams = [Stream() for i in range(num_outputs)]
    Agent(inputs, output_streams, transition, state, call_streams)
    return output_streams

def element_func(f, inputs, num_outputs, state, call_streams,
                 window_size, step_size):
    
    assert_is_list_of_streams_or_None(call_streams)

    def transition(in_lists, state):
        input_lists = zip(*[v.list[v.start:v.stop] for v in in_lists])
        # If the new input data is empty then return empty lists for
        # each output stream, and leave the state and the starting point
        # for each input stream unchanged.
        if not input_lists:
            return ([[]]*num_outputs, state, [v.start for v in in_lists])

        #list_of_output_list[i] will be set to the output value
        # corresponding to the i-th value in each of the input
        # streams
        list_of_output_list = [[]]*len(input_lists)
        for i,input_list in enumerate(input_lists):
            if state is None:
                output_list = f(input_list)
            else:
                output_list, state = f(input_list, state)
            # The output_list returned by f must have
            # one element for each output stream.
            # The output list must be a list; so convert
            # None values (for sinks) into empty lists.
            if output_list is None: output_list = []
            assert len(output_list) == num_outputs
            list_of_output_list[i] = output_list

        # This function has at least one output because the sink case
        # was considered in the last line.
        # list_of_output_list[i] is a list with one element for each output stream.
        # zip them up to get output_lists where output_lists[j] is the list that
        # gets appended to output stream j.
        output_lists = [list(v) for v in zip(*list_of_output_list)]
        # Remove _no_value elements from the output list because they do not
        # appear in streams.
        # Open up _multivalue([a,b]) into separate a, b values.
        output_lists = \
          [remove_novalue_and_open_multivalue(l) for l in output_lists]
        return (output_lists, state, [v.start+len(input_lists) for v in in_lists])

    # Create agent
    output_streams = [Stream() for i in range(num_outputs)]
    Agent(inputs, output_streams, transition, state, call_streams)
    return output_streams


def window_func(f, inputs, num_outputs, state, call_streams, window_size, step_size):
    #f: list, state -> element, state
    def transition(in_lists, state=None):
        range_out = range((num_outputs))
        range_in = range(len(in_lists))
        # This function will set the k-th element of output_lists
        # to the value to be output on the k-th output stream.
        output_lists = [ [] for _ in range_out ]
        # window_starts is the list of starting indices for the
        # window in each input stream.
        window_starts = [in_list.start for in_list in in_lists]

        smallest_list_length = min(v.stop - v.start for v in in_lists)
        if window_size > smallest_list_length:
            # Do not have enough elements in an input stream
            # for an operation on the window.
            # So no changes are made.
            return (output_lists, state, window_starts)

        # Each input stream has enough elements for a window operation.
        # num_steps is the number of window operations that can be
        # carried out with the given numbers of elements in the input streams.
        num_steps = 1 + (smallest_list_length - window_size)/step_size
        for i in range(num_steps):
            # Calculate the output, 'increments', for this window operation.
            # windows is a list with a window for each input stream.
            # increments[k] will be appended to the k-th output stream
            # by this function.
            windows = [in_lists[j].list[window_starts[j]:window_starts[j]+window_size] \
                       for j in range_in]
            if state is None:
                increments = f(windows)
            else:
                increments, state = f(windows, state)
                
            # Remove _no_value and open up _multivalue elements in
            # each [increments[k]].
            # Note that increments[k] is a value to be appended to
            # the output stream. The function remove_novalue.. has
            # a parameter which is a list. So we call the function
            # with parameter [increments[k]] rather than increments[k]
            # and we extend output_lists[k] rather than append to it.
            for k in range_out:
                output_lists[k].extend(
                    remove_novalue_and_open_multivalue([increments[k]]))

            window_starts = [v+step_size for v in window_starts]

        in_lists_start_values = [in_list.start + num_steps*step_size for in_list in in_lists]
        return (output_lists, state, in_lists_start_values)

    # Create agent
    output_streams = [Stream() for v in range(num_outputs)]
    Agent(inputs, output_streams, transition, state, call_streams)

    return output_streams



def list_index_for_timestamp(in_list, start_index, timestamp):
    """ A helper function for timed operators.
    The basic idea is to return the earliest index in
    in_list.list with a time field that is greater than
    or equal to timestamp. If no such index exists then
    return a negative number.

    Returns positive integer i where:
    either: 'FOUND TIME WINDOW IN IN_LIST'
        i > start_index and
        i <= in_list.stop  and
        in_list.list[i-1].time >= timestamp and
        (i == start_index+1 or in_list.list[i-2].time < timestamp)
    or: 'NO TIME WINDOW IN IN_LIST'
        i < 0 and
           (in_list.list[in_list.stop-1] <= timestamp
                       or
           (in_list.start = in_list.stop)

    Requires:
         start_index >= in_list.start and
         start_index < in_list.stop

    """
    if in_list.start == in_list.stop: return -1

    if start_index < in_list.start or start_index >= in_list.stop:
        raise Exception('start_index out of range: start_index =', start_index,
                        ' in_list.start = ', in_list.start,
                        ' in_list.stop = ', in_list.stop)
    for i in range(start_index, in_list.stop):
        # assert i <= in_list.stop-1
        if in_list.list[i].time >= timestamp:
            return i
    # assert in_list.list[in_list.stop - 1] < timestamp
    return -1


def timed_func(f, inputs, num_outputs, state, call_streams, window_size, step_size):
    # inputs is a list of lists of TimeAndValue pairs.
    range_out = range((num_outputs))
    range_in = range(len(inputs))
    window_start_time = 0
    combined_state = (window_start_time, state)

    def transition(in_lists, combined_state):
        window_start_time, state = combined_state
        output_lists = [ [] for _ in range_out]
        window_end_time = window_start_time + window_size
        window_start_indexes = [ in_lists[j].start for j in range_in]
        while True:
            # window_end_indexes is a list where its j-th
            # element is either the earliest index in the j-th
            # input stream for which the stream element's time
            # is at least window_end_time, or is a negative
            # number if no such element exists in the stream.
            window_end_indexes = [list_index_for_timestamp(
                in_lists[j],
                window_start_indexes[j],
                window_end_time) for j in range_in]
            # If any time window is empty then do not
            # carry out computations across the time windows
            # of all the input streams. Return with no change
            # to window_start_time or the state, and with
            # the output_list for each stream set to the empty
            # list.
            if any(window_end_indexes[j] < 0 for j in range_in):
                break
            # Assert all of the time windows are non-empty, i.e.,
            # for each input stream j:
            # window_end_indexes[j] > window_start_indexes[j]
            windows = [in_lists[j].list[window_start_indexes[j]: \
                                       window_end_indexes[j]] for j in range_in]
            # windows is a list where:
            # windows[j] is a list of TimeAndValue objects.
            # Function f returns a list of ordinary objects (i.e., these
            # objects are typically not TimeAndValue objects).
            # increments[k] is the output list for the k-th output stream.
            if state is None:
                increments = f(windows)
            else:
                increments, state = f(windows, state)

            # The output for each output stream contains TimeAndValue objects.
            # The time field for all of the objects is the same: window_end_time.
            for k in range_out:
                output_lists[k].append(TimeAndValue(window_end_time, increments[k]))
            window_start_time += step_size
            window_end_time += step_size
            new_window_start_indexes = [list_index_for_timestamp(
                in_lists[j],
                window_start_indexes[j],
                window_start_time) for j in range_in]
            if any(new_window_start_indexes[j] < 0 for j in range_in):
                break
            ## #CHECKING FOR PROGRESS TOWARDS TERMINATION
            ## if (any(new_window_start_indexes[j] < window_start_indexes[j]
            ##        for j in range_in) or
            ##        all(new_window_start_indexes[j] == window_start_indexes[j]
            ##        for j in range_in)):
            ##     raise Exception('TimedOperator: start_indexes')
            window_start_indexes = new_window_start_indexes

        combined_state = (window_start_time, state)
        return (output_lists, combined_state, window_start_indexes)
    # Create agent
    out_streams = [Stream() for v in range(num_outputs)]
    combined_state = (window_start_time, state)
    Agent(inputs, out_streams, transition, combined_state)

    return out_streams


def asynch_element_func(
        f, inputs, num_outputs, state, call_streams,
        window_size, step_size):
    
    assert_is_list_of_streams_or_None(call_streams)

    def transition(in_lists, state):
        # If the input data is empty then return empty lists for
        # each output stream, and leave the state and the starting point
        # for each input stream unchanged.
        if all(v.stop <= v.start for v in in_lists):
            return ([[]]*num_outputs, state, [v.start for v in in_lists])

        # Assert at least one input stream has unprocessed data.
        
        # output_lists[j] will be sent on output stream j
        output_lists = [[]]*num_outputs
        for stream_number, v in enumerate(in_lists):
            # if v.stop <= v.start then skip this input stream
            if v.stop > v.start:
                # Carry out a state transition for this input
                # stream.
                # input_list is the list of new values on this
                # stream. Compute the incremental list generated
                # by each element in input list due to a transition,
                # i.e., an execution of f.
                input_list = v.list[v.start:v.stop]
                for element in input_list:
                    if state is None:
                        output_lists_increment = \
                          f((element, stream_number))
                    else:
                        # This function has state.
                        output_lists_increment, state = \
                          f((element, stream_number), state)
                    assert len(output_lists_increment) == num_outputs
                    for k in range(num_outputs):
                        output_lists[k].append(output_lists_increment[k])
        return (output_lists, state, [v.stop for v in in_lists])

    
    # Create agent
    output_streams = [Stream() for i in range(num_outputs)]
    Agent(inputs, output_streams, transition, state, call_streams)
    return output_streams


"""
PART 2 OF MODULE.
Functions that map the general case of an arbitrary
number of input streams and output streams to the special cases
of merge, split, op, source and sink.

Each of these functions has the following parameters:
f, h, in_streams, window_size, step_size, state, call_streams.

Parameters
----------
f_type: str
   function on a standard Python data structure such as an
   integer or a list.
f: A general case (muti-input, multi-output) function.
in_streams: A list of input streams
window_size: Either None or a positive integer
step_size: None if the window_size is None, otherwise a positive
          integer.
state: The state of the computation.
call_streams: A list of streams. When a value is appended to any
      stream in this list, the function is executed.

merge: list of input streams, single output stream
split: single input stream, list of output streams
op: single input and single output stream
source: no input
f, in_streams, state, call_streams, window_size, step_size)
"""


def h(f_type, *args):
    if f_type is 'list':
        return list_func(*args)
    elif f_type is 'element':
        return element_func(*args)
    elif f_type is 'window':
        return window_func(*args)
    elif f_type is 'timed':
        return timed_func(*args)
    elif f_type is 'asynch_element':
        return asynch_element_func(*args)
    else:
        return 'no match'

def many_to_many(f_type, f, in_streams, num_outputs, state,
                 call_streams, window_size, step_size):
    def g(x, state=None):
        if state is None: return f(x)
        else:
            output, new_state = f(x, state)
            return (output, new_state)

    out_streams = h(f_type, g, in_streams, num_outputs, state,
                    call_streams, window_size, step_size)
    return out_streams


def merge(f_type, f, in_streams, state, call_streams, window_size, step_size):
    def g(x, state=None):
        if state is None: return [f(x)]
        else:
            output, new_state = f(x, state)
            return ([output], new_state)

    out_streams = h(f_type, g, in_streams, 1, state, call_streams,
                    window_size, step_size)
    return out_streams[0]

    
def split(f_type, f, in_stream, num_outputs, state, call_streams, window_size, step_size):
    def g(x, state=None):
        if state is None: return f(x[0])
        else:
            #output, new_state = f(x[0], state)
            # return (output, new_state)
            return f(x[0], state)

    out_streams = h(f_type, g, [in_stream], num_outputs, state, call_streams,
                    window_size, step_size)
    return out_streams


def op(f_type, f, in_stream, state, call_streams, window_size, step_size):
    def g(x, state=None):
        if state is None:
            return [f(x[0])]
        else:
            output, new_state = f(x[0], state)
            return ([output], new_state)

    out_streams = h(f_type, g, [in_stream], 1, state, call_streams,
                    window_size, step_size)
    return out_streams[0]


def single_output_source(f_type, f, num_outputs, state, call_streams,
                         window_size, step_size):

    def g(x, state=None):
        if state is None: return [f()]
        else: return [f(state)]

    out_streams = h(f_type, g, call_streams, num_outputs, state, call_streams,
                    window_size, step_size)
    return out_streams[0]

def many_outputs_source(f_type, f, num_outputs, state, call_streams,
                        window_size, step_size):
    def g(x, state=None):
        if state is None: return f()
        else:
            #output, new_state = f(state)
            return f(state)

    out_streams = h(f_type, g, call_streams, num_outputs, state, call_streams,
                    window_size, step_size)
    return out_streams


def sink(f_type, f, in_stream, state, call_streams, window_size, step_size):
    def g(x, state=None):
        #assert state is None
        if state is None: return f(x[0])
        else: return f(x[0], state)

    out_streams = h(f_type, g, [in_stream], 0, state, call_streams,
                    window_size, step_size)
    return out_streams



""" PART 3 OF MODULE.
A function, stream_func, that provides a single common signature for
converting operations on Python structures to operations on streams
regardless of whether the function has no inputs, a single input stream,
a list of input streams, or no outputs, a single output stream or a
list of output streams.
"""


def stream_func(inputs, f_type, f, num_outputs, state=None, call_streams=None,
                window_size=None, step_size=None):
    """ Provides a common signature for converting functions f on standard
    Python data structures to streams.

    Parameters
    ----------
    f_type : {'element', 'list', 'window', 'timed', 'asynch_element'}
       f_type identifies the type of function f where f is the next parameter.
    f : function
    inputs : {Stream, list of Streams}
       When stream_func has:
          no input streams, inputs is None
          a single input Stream, inputs is a single Stream
          multiple input Streams, inputs is a list of Streams.
    num_outputs : int
       A nonnegative integer which is the number of output streams of
       this function.
    state : object
       state is None or is an arbitrary object. The state captures
       all the information necessary to continue processing the input
       streams.
    call_streams : None or list of Stream
       If call_streams is None then the program sets it to inputs
       (converting inputs to a list of Stream if necessary).
       This function is called when, and only when any stream in
       call_streams is modified.
    window_size : None or int
       window_size must be a positive integer if f_type is 'window'
       or 'timed'. window_size is the size of the moving window on
       which the function operates.
    step_size : None or int
       step_size must be a positive integer if f_type is 'window'
       or 'timed'. step_size is the number of steps by which the
       moving window moves on each execution of the function.

    Returns
    -------
    list of Streams
       Function f is applied to the appropriate data structure in
       the input streams to put values in the output streams.
       stream_func returns the output streams.
    """

    # Check types of parameters
    if not isinstance(num_outputs, int):
        raise TypeError('Expected num_outputs to be int, not:',
                        num_outputs)
    if num_outputs < 0:
        raise ValueError('Expected num_outputs to be nonnegative, not:',
                         num_outputs)
    
    if not((inputs is None) or
           (isinstance(inputs, Stream) or
           ((isinstance(inputs, list) and
             (all(isinstance(l, Stream) for l in inputs))
             )
           ))):
        raise TypeError('Expected inputs to be None, Stream or list of Streams, not:',
                        inputs)

    if not((call_streams is None) or
           ((isinstance(call_streams, list) and
             (all(isinstance(l, Stream) for l in call_streams))
             )
           )):
        raise TypeError('Expected call_streams to be None, Stream or list of Streams, not:',
                        call_streams)

    if inputs is None:
        # Check that call_streams is nonempty
        if len(call_streams) < 1:
            raise TypeError('Expected call_streams to be a nonempty list of streams, not:',
                        call_streams)
    
        if num_outputs == 0:
            raise TypeError('The function has no input or output streams.')
    
        elif num_outputs == 1:
            # No inputs. Single output stream.
            return single_output_source(f_type, f, num_outputs,
                                        state, call_streams,
                                        window_size, step_size)
        else:
            # No inputs. List of multiple output streams.
            return many_outputs_source(f_type, f, num_outputs,
                                       state, call_streams,
                                       window_size, step_size)

    elif isinstance(inputs, Stream) or isinstance(inputs, StreamArray):
        in_stream = inputs
        if num_outputs == 0:
            # Single input stream. No outputs.
            return sink(f_type, f, in_stream, state, call_streams,
                        window_size, step_size)
        elif num_outputs == 1:
            # Single input stream. Single output stream.
            return op(f_type, f, in_stream, state, call_streams, window_size, step_size)
        else:
            # Single input stream. List of multiple output streams.
            return split(f_type, f, in_stream, num_outputs, state, call_streams,
                         window_size, step_size)

    else:
        # Multiple input streams
        if num_outputs == 0:
            # sink
            raise TypeError('A sink has exactly one input stream.')
        elif num_outputs == 1:
            # Multiple input streams, single output stream
            return merge(f_type, f, inputs, state, call_streams, window_size, step_size)
        else:
            # Multiple input and output streams
            return many_to_many(f_type, f, inputs, num_outputs, state, call_streams, window_size, step_size)


def main():
    def squares(l):
        return [v*v for v in l]
    def sums(v, state):
        return (v+state, v+state)
    def sums_asynch(v_and_i, state):
        v,i = v_and_i
        return (v+state, v+state)
    def max_min(v_and_i, state):
        max_so_far, min_so_far = state
        v,i = v_and_i
        max_so_far = max(max_so_far, v)
        min_so_far = min(min_so_far, v)
        state = max_so_far, min_so_far
        return([max_so_far, min_so_far], state)

    x_stream = Stream('x')
    w_stream = Stream('w')

    y_stream = stream_func(
        inputs=x_stream,
        f_type='element',
        f=sums,
        state=0.0,
        num_outputs=1)
    y_stream.set_name('cumulative sum of x')

    z_stream = stream_func(
        inputs=[x_stream, w_stream],
        f_type='asynch_element',
        f=sums_asynch,
        state=0.0,
        num_outputs=1)
    z_stream.set_name('asynch element. Cumulative sum of x')

    r_stream, s_stream = stream_func(
        inputs=[x_stream, w_stream],
        f_type='asynch_element',
        f=max_min,
        state=(0, 1000),
        num_outputs=2)
    r_stream.set_name('asynch element. max of x and w')
    s_stream.set_name('asynch element. min of x and w')

    

    x_stream.extend(range(5))
    w_stream.extend([100, -1, 10, 201, -31, 72])
    x_stream.print_recent()
    w_stream.print_recent()
    y_stream.print_recent()
    z_stream.print_recent()
    r_stream.print_recent()
    s_stream.print_recent()

if __name__ == '__main__':
    main()
    




