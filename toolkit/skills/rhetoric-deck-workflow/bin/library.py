from rdw import main

if __name__ == "__main__":
    raise SystemExit(main(["library", *(__import__("sys").argv[1:])]))
