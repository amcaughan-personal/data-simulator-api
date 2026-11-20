resource "aws_s3_bucket" "deliberately_insecure" {
  bucket = "comment-test-do-not-merge"
}
