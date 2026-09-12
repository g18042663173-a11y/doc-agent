from rdw import main

if __name__ == "__main__":
    raise SystemExit(main(["seal", *(__import__("sys").argv[1:])]))

