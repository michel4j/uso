from misc.blocktypes import BaseBlock, BLOCK_TYPES


class ProfileBlock(BaseBlock):
    block_type = BLOCK_TYPES.dashboard
    template_name = "users/blocks/profile.html"
    priority = 0


