#!/usr/bin/perl

# Linbot mtr add-on     Yaakov (08-06-2009)  ver .1b
# /msg alias add mtr-newark web title http://kovaya.com/mtr.cgi?target_host=$1

use strict;
use warnings;

use CGI;
my $q=new CGI;

if ($ENV{REMOTE_ADDR} ne "67.18.186.57") {
  print $q->header;
  print "<h1>GO AWAY</h1>";
  exit;
}

my $return; 

my $host = $q->param('target_host');
  $host =~ s/^[^\w\d\.\-_]+$//;
  
if ($host eq "") {
  
    print $q->header;

print <<HEADER
<head>
  <title>[mtr] no host given</title>
<head>
HEADER
;

  exit;
}

my @results = qx/mtr -4 --report --report-cycles 5 $host 2>&1/;
  if ($results[0] =~ 'not known') {

    print $q->header;

print <<HEADER
<head>
  <title>[mtr] $host: not found</title>
<head>
HEADER
;

  exit;
}

shift @results;
  my $hops = scalar @results;
  
my $last_hop_rtt;

for my $line (@results) {
  my @fields = split /\s+/, $line;
    my (undef, undef, $host, $loss, undef, undef, $avg_rtt) = @fields;
  $last_hop_rtt = $avg_rtt;
  $loss =~ s/%//;
  next if not int($loss);
  
  $return .=', ' if $return;
  $return .= "$host: $loss%/${avg_rtt}ms";  
}

my $report = $return || "no loss, last hop average RTT was ${last_hop_rtt}ms";

print $q->header;
print <<HEADER
<head>
  <title>[mtr] $host: $hops hops, $report</title>
<head>
HEADER
;
