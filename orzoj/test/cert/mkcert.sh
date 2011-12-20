#!/bin/bash -e
LEN=4096

openssl genrsa -out ca.key $LEN
openssl req -new -x509 -days 365 -key ca.key -out ca.crt

serial=1
for i in server client
do
	openssl genrsa -out $i.key $LEN
	openssl req -new -key $i.key -out $i.csr

	openssl x509 -req -days 365 -in $i.csr -CA ca.crt -CAkey ca.key \
		-set_serial 0$serial -out $i.crt
	let serial=$serial+1
done
