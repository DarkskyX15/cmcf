int add(int a, int b) { return a + b; }
int sub(int a, int b) { return a - b; }
int mul(int a, int b) { return a * b; }
int sdiv(int a, int b) { return a / b; }

static int local_helper(void) { return 42; }

int get_local(void) { return local_helper(); }
