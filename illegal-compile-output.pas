var
a,b:longint;
begin
assign(input,‘a+b.in');
assign(output,'a+b.out');
reset(input);
rewrite(output);
readln(a,b);
writeln(a+b);
close(input);
close(output);
end.
