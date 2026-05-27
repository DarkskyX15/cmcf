int square(int x) {
    return x * x;
}

int sum(int a, int b) {
    return a + b;
}

int main(void) {
    int a = 3;
    int b = 7;
    int s = sum(a, b);
    int sq = square(s);
    return sq;
}
