extern int add(int a, int b);
extern int sub(int a, int b);
extern int mul(int a, int b);
extern int sdiv(int a, int b);
extern int get_local(void);

int main(void) {
    return add(10, 3) + sub(10, 3) + mul(10, 3) + sdiv(10, 3) + get_local();
}
