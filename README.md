# orzoj.server-judge
Automatically exported from code.google.com/p/orzoj.server-judge

# original readme

*orzoj is deprecated. It will be replaced by https://github.com/jia-kai/pynojo .

Orzoj is an open source cross-platform online judge system which is designed to be secure, efficient and highly extensible.

Highlighted features:

  * website is pure PHP without requiring special permission (e.g. executing external binaries), so you can host the website anywhere, instead of buying a fully-permitted server.
  * website supports various databases, including but not limited to MySQL and  PostgreSQL.
  * plugins and themes are supported by PHP website
  * problem test data are stored on orzoj-server, so it's secure and easy to manage (usually orzoj-server is a local host with high network speed, which allows you to upload and modify data quickly)
  * communication between orzoj-server and orzoj-judge are SSL encrypted with bilateral authentication
  * multiple judges are supported with automatic load-balancing (although the balancing algorithm is not very advanced currently)
  * easy to configure and highly user definable (see problem configuration file format and orzoj-judge configuration file for details)
