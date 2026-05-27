static int helper(void) { return 1; }

int plus_one(int x) { return x + helper(); }
int plus_two(int x) { return x + helper() + helper(); }
