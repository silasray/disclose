disclose
========

`disclose` is a library that eases reporting and management of validation
 steps in tests.  It handles logging the activity, state, and outcome of
 validation steps, as well as providing a facility to collect results and
 interrogate overall result state.

Installation
============

`disclose` is on pypi.  Install with `pip install disclose`.

Quickstart
==========

The most basic usage of `disclose` is to create a `VerificationSession`
 instance, call it with statements, and then assert the session at the end.

    import disclose
    
    # Just here so we get our logging shunted to stderr easily
    from logging import basicConfig
    basicConfig(level='DEBUG')
    
    verify = disclose.VerificationSession()
    verify(1 == 1)
    verify(2 + 3 == 5)
    verify(3 / 2 == 2)
    assert verify, 'Some verification failed!'

This will log each verification step as it is executed, and tell us the state
 of the expression.  `VerificationSession` instances are falsey if they have
 verified any failing statements, so `assert verify` will assert if any of the
 verification steps are failed.  Our output will be:
 
    INFO:test.validation:::VERIFICATION PASSED::
    True
    INFO:test.validation:::VERIFICATION PASSED::
    True
    ERROR:test.validation:::VERIFICATION FAILED::
    False
    <trace here>
    Traceback (most recent call last):
      File (...)
        assert verify, 'Some verification failed!'
    AssertionError: Some verification failed!

This is nice, but the real power of `disclose` comes in to play when we start
 using `OperandWrapper` to wrap operands in our verification statements.
  `OperandWrapper` creates a shadow object that records metadata about the
 proxied object, and returns `OperandWrapper` proxies when that object is used
 in statements or attribute access or other manipulations are performed on the
 object.  These shadow objects are used in turn by `VerificationSession`
 instances to log information about the verification performed.  An object
 wrapped in an `OperandWrappper` (and all its derivatives) will continue to
 operate just like the proxied object, except will have the additional
 functionality in the context of a `VerificationSession`.
 
    from disclose import VerificationSession, OperandWrapper
    
    from logging import basicConfig
    basicConfig(level='DEBUG')
    
    verify = VerificationSession()
    a = OperandWrapper(2, 'a')
    b = OperandWrapper(3, 'b')
    verify(a == b)
    
    class Foo(object):
        
        def __init__(self, x, child=None):
            
            self.x = x
            self.child = child
    
    foo_a = OperandWrapper(Foo(4), 'foo_a')
    foo_b = OperandWrapper(Foo(5, foo_a))
    verify(foo_a.x == 4)
    verify(foo_b.x = 5)
    verify(foo_b.child.x == foo_a.x)
    verify(foo_a.x + 2 == 6)
    verify(foo_a.x < 4)
    foo_a.x = 2
    verify(foo_a.x < 4)

`verify` pulls the shadow object for each proxied object out, then constructs
 useful logging messages out of all the metadata attached.  It will reconstruct
 (to as deep a level as shadow objects are available) the statement verified,
 and dump the state of all the arguments (at least all the ones which it can
 find shadow objects for) in the expression to another log message.  We'll see:
 
    ERROR:test.validation:::VERIFICATION FAILED::
    (a) == (b)
    DEBUG:test.validation:a = 2
    b = 3
    <trace here>
    INFO:test.validation:::VERIFICATION PASSED::
    (foo_a.x) == (4)
    DEBUG:test.validation:foo_a = <__main__.Foo object at 0x7f5753c94a50>
    foo_a.x = 4
    INFO:test.validation:::VERIFICATION PASSED::
    (Foo.x) == (5)
    DEBUG:test.validation:Foo = <__main__.Foo object at 0x7f5753c94b10>
    Foo.x = 5
    INFO:test.validation:::VERIFICATION PASSED::
    (Foo.child.x) == (foo_a.x)
    DEBUG:test.validation:Foo = <__main__.Foo object at 0x7f5753c94b10>
    Foo.child = <__main__.Foo object at 0x7f5753c94a50>
    Foo.child.x = 4
    foo_a = <__main__.Foo object at 0x7f5753c94a50>
    foo_a.x = 4
    INFO:test.validation:::VERIFICATION PASSED::
    ((foo_a.x) + (2)) == (6)
    DEBUG:test.validation:foo_a = <__main__.Foo object at 0x7f5753c94a50>
    foo_a.x = 4
    (foo_a.x) + (2) = 6
    ERROR:test.validation:::VERIFICATION FAILED::
    (foo_a.x) < (4)
    <trace here>
    DEBUG:test.validation:foo_a = <__main__.Foo object at 0x7f5753c94a50>
    foo_a.x = 4
    INFO:test.validation:::VERIFICATION PASSED::
    (foo_a.x) < (4)
    DEBUG:test.validation:foo_a = <__main__.Foo object at 0x7f5753c94a50>
    foo_a.x = 2

Note that the system is aware of the names for the top level variables.  This
 is because of the optional second argument to `OperandWrapper`, which will
 become the name of the operand within `disclose`.  When not included, the
 system falls back to automatic name generation (as seen with `foo_b`, which
 is displayed with the class name here).

The `VerifcationSession` can also be used as a context manager.  In this mode,
 when the context manager is exited, any assertions from within the context
 will be handled by the `VerificationSession` as well.  The following is
 essentially functionally identical to the previous example.
 
    from disclose import VerificationSession, OperandWrapper
    
    from logging import basicConfig
    basicConfig(level='DEBUG')
    
    
    class Foo(object):
        
        def __init__(self, x, child=None):
            
            self.x = x
            self.child = child
    
    
    with VerificationSession() as verify:
        a = OperandWrapper(2, 'a')
        b = OperandWrapper(3, 'b')
        verify(a == b)
        foo_a = OperandWrapper(Foo(4), 'foo_a')
        foo_b = OperandWrapper(Foo(5, foo_a))
        verify(foo_a.x == 4)
        verify(foo_b.x = 5)
        verify(foo_b.child.x == foo_a.x)
        verify(foo_a.x + 2 == 6)
        verify(foo_a.x < 4)
        foo_a.x = 2
        verify(foo_a.x < 4)

Note
====

The proxy markup will propegate with attribute access, key/index access,
 and iteration, but type conversion, length, and truth testing operations
 currently break the markup system.