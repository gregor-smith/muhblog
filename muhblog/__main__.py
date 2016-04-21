try:
    from ._muhblog import main
except SystemError:
    from _muhblog import main

main()
