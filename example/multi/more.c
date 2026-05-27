extern int plus_one(int x);
extern int plus_two(int x);

int compute(int base) {
    return plus_one(base) + plus_two(base);
}
