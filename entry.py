import sys
if '--server' in sys.argv:
    sys.argv.remove('--server')
    from run import main
else:
    from desktop_launcher import main
if __name__=='__main__': raise SystemExit(main())
