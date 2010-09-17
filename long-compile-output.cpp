#define A(x) x##x##x##x
#define B(x) x##x##x##x
#define XB(x) B(x)
#define C(x) x##x##x##x
#define XC(x) C(x)
#define D(x) x##x##x##x
#define XD(x) D(x)
#define E(x) x##x##x##x
#define XE(x) E(x)
#define F(x) x##x##x##x
#define XF(x) F(x)
#define G(x) x##x##x##x
#define XG(x) G(x)
#define H(x) x##x##x##x
#define XH(x) H(x)
#define I(x) x##x##x##x
#define XI(x) I(x)
#define J(x) x##x##x##x
#define XJ(x) J(x)
#define K(x) x##x##x##x
#define XK(x) K(x)
#define L(x) x##x##x##x
#define XL(x) L(x)
#define M(x) x##x##x##x
#define XM(x) M(x)

int main()
{
	XM(XL(XK(XJ(XI(XH(XG(XF(XE(XD(XC(XB(A(x))))))))))))) = 0;
}

