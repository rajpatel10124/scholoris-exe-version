resource "aws_efs_file_system" "fs" {
  creation_token = "scholaris-efs"
  tags           = { Name = "scholaris-efs" }
}

resource "aws_efs_mount_target" "mount_a" {
  file_system_id  = aws_efs_file_system.fs.id
  subnet_id       = aws_subnet.public_a.id
  security_groups = [aws_security_group.ec2_sg.id]
}

resource "aws_efs_mount_target" "mount_b" {
  file_system_id  = aws_efs_file_system.fs.id
  subnet_id       = aws_subnet.public_b.id
  security_groups = [aws_security_group.ec2_sg.id]
}
