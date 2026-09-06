from rdw import main

if __name__ == "__main__":
    raise SystemExit(main(["doctor", *(__import__("sys").argv[1:])]))

