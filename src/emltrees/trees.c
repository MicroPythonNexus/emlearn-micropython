// Include the header file to get access to the MicroPython API
#include "py/dynruntime.h"

#define EML_TREES_REGRESSION_ENABLE 0
#include <eml_trees.h>

#include <string.h>

// memset is used by some standard C constructs
#if !defined(__linux__)
void *memcpy(void *dst, const void *src, size_t n) {
    return mp_fun_table.memmove_(dst, src, n);
}
void *memset(void *s, int c, size_t n) {
    return mp_fun_table.memset_(s, c, n);
}
#endif


// For building up an EmlTrees structure
typedef struct _EmlTreesBuilder {
    EmlTrees trees;
    int max_nodes;
    int max_trees;
} EmlTreesBuilder;

// MicroPython type for EmlTreesBuilder
typedef struct _mp_obj_trees_builder_t {
    mp_obj_base_t base;
    EmlTreesBuilder builder;
} mp_obj_trees_builder_t;

mp_obj_full_type_t trees_builder_type;

// Create a new tree builder
STATIC mp_obj_t builder_new(mp_obj_t trees_obj, mp_obj_t nodes_obj) {

    mp_int_t max_nodes = mp_obj_get_int(nodes_obj);
    mp_int_t max_trees = mp_obj_get_int(trees_obj);

    //mp_printf(&mp_plat_print, "builder-new nodes=%d trees=%d\n", max_nodes, max_trees);

    // create builder
    mp_obj_trees_builder_t *o = mp_obj_malloc(mp_obj_trees_builder_t, (mp_obj_type_t *)&trees_builder_type);

    EmlTreesBuilder *self = &o->builder;

    memset(self, 1, sizeof(EmlTreesBuilder)); // HACK: try to get memset symbol in

    self->max_nodes = max_nodes;
    self->max_trees = max_trees;

    // create trees
    EmlTreesNode *nodes = (EmlTreesNode *)m_malloc(sizeof(EmlTreesNode)*max_nodes);
    int32_t *roots = (int32_t *)m_malloc(sizeof(int32_t)*max_trees);

    mp_printf(&mp_plat_print, "emltrees nodes=%p roots=%p builder=%p\n", nodes, roots, self);

    self->trees.n_nodes = 0;
    self->trees.nodes = nodes;
    self->trees.n_trees = 0;
    self->trees.tree_roots = roots;

    return MP_OBJ_FROM_PTR(o);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(builder_new_obj, builder_new);

// Delete a tree builder
STATIC mp_obj_t builder_del(mp_obj_t trees_obj) {

    mp_obj_trees_builder_t *o = MP_OBJ_TO_PTR(trees_obj);
    EmlTreesBuilder *self = &o->builder;

    // free allocated data
    m_free(self->trees.nodes);
    m_free(self->trees.tree_roots);

    mp_printf(&mp_plat_print, "emltrees del \n");

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(builder_del_obj, builder_del);


// Add a node to the tree
STATIC mp_obj_t builder_addnode(size_t n_args, const mp_obj_t *args) {

    mp_obj_trees_builder_t *o = MP_OBJ_TO_PTR(args[0]);
    EmlTreesBuilder *self = &o->builder;    

    const int16_t left = mp_obj_get_int(args[1]);
    const int16_t right = mp_obj_get_int(args[2]);
    const int8_t feature = mp_obj_get_int(args[3]);
    const int16_t value = mp_obj_get_int(args[4]);

    if (self->trees.n_nodes >= self->max_nodes) {
        mp_raise_ValueError(MP_ERROR_TEXT("max nodes"));
    }

    const int node_index = self->trees.n_nodes++;
    self->trees.nodes[node_index] = (EmlTreesNode){ feature, value, left, right };

    return mp_const_none;
 }
STATIC MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(builder_addnode_obj, 5, 5, builder_addnode);


// Add a node to the tree
STATIC mp_obj_t builder_addroot(size_t n_args, const mp_obj_t *args) {

    mp_obj_trees_builder_t *o = MP_OBJ_TO_PTR(args[0]);
    EmlTreesBuilder *self = &o->builder;    

    const int16_t root = mp_obj_get_int(args[1]);

    if (self->trees.n_trees >= self->max_trees) {
        mp_raise_ValueError(MP_ERROR_TEXT("max trees"));
    }

    const int root_index = self->trees.n_trees++;
    self->trees.tree_roots[root_index] = root; 

    return mp_const_none;
 }
STATIC MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(builder_addroot_obj, 2, 2, builder_addroot);




// Takes a array of input data
STATIC mp_obj_t predict(mp_obj_fun_bc_t *self_obj, size_t n_args, size_t n_kw, mp_obj_t *args) {
    // Check number of arguments is valid
    mp_arg_check_num(n_args, n_kw, 2, 2, false);

    mp_obj_trees_builder_t *o = MP_OBJ_TO_PTR(args[0]);
    EmlTreesBuilder *self = &o->builder;    

    // Extract buffer pointer and verify typecode
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[1], &bufinfo, MP_BUFFER_RW);
    if (bufinfo.typecode != 'h') {
        mp_raise_ValueError(MP_ERROR_TEXT("expecting int16 (h) array"));
    }

    const int16_t *features = bufinfo.buf;
    const int n_features = bufinfo.len / sizeof(*features);

    // call model
    const int result = eml_trees_predict(&self->trees, features, n_features);

    return mp_obj_new_int(result);
}


mp_map_elem_t trees_locals_dict_table[4];
STATIC MP_DEFINE_CONST_DICT(trees_locals_dict, trees_locals_dict_table);

// This is the entry point and is called when the module is imported
mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    // This must be first, it sets up the globals dict and other things
    MP_DYNRUNTIME_INIT_ENTRY

    mp_store_global(MP_QSTR_new, MP_OBJ_FROM_PTR(&builder_new_obj));

    trees_builder_type.base.type = (void*)&mp_fun_table.type_type;
    trees_builder_type.flags = MP_TYPE_FLAG_ITER_IS_CUSTOM;
    trees_builder_type.name = MP_QSTR_emltrees;
    // methods
    trees_locals_dict_table[0] = (mp_map_elem_t){ MP_OBJ_NEW_QSTR(MP_QSTR_predict), MP_DYNRUNTIME_MAKE_FUNCTION(predict) };
    trees_locals_dict_table[1] = (mp_map_elem_t){ MP_OBJ_NEW_QSTR(MP_QSTR_addnode), MP_OBJ_FROM_PTR(&builder_addnode_obj) };
    trees_locals_dict_table[2] = (mp_map_elem_t){ MP_OBJ_NEW_QSTR(MP_QSTR_addroot), MP_OBJ_FROM_PTR(&builder_addroot_obj) };
    trees_locals_dict_table[3] = (mp_map_elem_t){ MP_OBJ_NEW_QSTR(MP_QSTR___del__), MP_OBJ_FROM_PTR(&builder_del_obj) };

    MP_OBJ_TYPE_SET_SLOT(&trees_builder_type, locals_dict, (void*)&trees_locals_dict, 4);

    // This must be last, it restores the globals dict
    MP_DYNRUNTIME_INIT_EXIT
}

