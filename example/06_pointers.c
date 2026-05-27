int main(void) {
    int x = 42;
    int *p = &x;
    *p = 100;
    int y = *p;
    return y;
}
